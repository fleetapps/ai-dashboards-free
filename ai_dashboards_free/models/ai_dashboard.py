# -*- coding: utf-8 -*-
"""The dashboard record.

A dashboard is a *saved question*, not a saved answer. ``spec_json`` holds
which models to read, how to filter and how to group; it never holds a number.
Everything is calculated when somebody opens it, as that person, through the
ORM - which is what makes a shared dashboard safe to share and impossible to
leave stale.

Deliberately not an ``ir.ui.menu``. Only ``base.group_system`` may create menus
(base/security/ir.model.access.csv), so a dashboard built by an assistant
running as an ordinary employee could not be one without handing every employee
the power to rewrite the database's navigation. A record in this model, reached
through the app tile, needs no elevated rights at all - and gets ownership,
sharing and per-group visibility for free, which real menu items would have
made painful.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from . import ai_dashboard_spec as spec_lib

_logger = logging.getLogger(__name__)

GROUP_USER = "ai_dashboards_free.group_dashboard_user"
GROUP_ADMIN = "ai_dashboards_free.group_dashboard_admin"


class AIDashboard(models.Model):
    _name = "ai.dashboard"
    _description = "AI Dashboard"
    _inherit = ["mail.thread"]
    _order = "sequence, name"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(help="Kanban colour, for the person's own sorting.")

    spec_json = fields.Text(
        string="Specification", required=True, default="{}",
        help="The validated dashboard specification. Holds the questions this "
             "dashboard asks - never any data.")
    description = fields.Text(
        help="What this dashboard shows, in the words of whoever built it.")
    explanation = fields.Text(
        compute="_compute_explanation",
        help="A plain-English account of exactly what this dashboard reads.")

    state = fields.Selection(
        [("draft", "Draft"), ("published", "Live")],
        default="draft", required=True, tracking=True,
        help="A preview is visible only to its owner and never appears on the "
             "app tile. Nothing an assistant builds is saved until a person "
             "has looked at it.")

    owner_id = fields.Many2one(
        "res.users", string="Owner", required=True, index=True,
        default=lambda self: self.env.user, ondelete="cascade")
    favorite_user_ids = fields.Many2many(
        "res.users", "ai_dashboard_favorite_rel", "dashboard_id", "user_id",
        string="Favourites", copy=False)
    is_favorite = fields.Boolean(
        compute="_compute_is_favorite", inverse="_inverse_is_favorite",
        search="_search_is_favorite")

    version_ids = fields.One2many(
        "ai.dashboard.version", "dashboard_id", string="History")
    version_count = fields.Integer(compute="_compute_version_count")

    last_render_ms = fields.Integer(
        string="Last render (ms)", readonly=True,
        help="How long the most recent open took to gather its figures.")
    is_slow = fields.Boolean(compute="_compute_is_slow")

    built_by_ai = fields.Boolean(
        default=False, readonly=True,
        help="Set when a dashboard arrived through an AI assistant rather than "
             "being made by hand.")

    # A dashboard an administrator has deliberately promoted to the main menu.
    pinned_menu_id = fields.Many2one(
        "ir.ui.menu", readonly=True, copy=False, ondelete="set null")
    is_pinned = fields.Boolean(compute="_compute_is_pinned")

    # ------------------------------------------------------------- computes
    @api.depends_context("uid")
    @api.depends("favorite_user_ids")
    def _compute_is_favorite(self):
        for rec in self:
            rec.is_favorite = self.env.user in rec.favorite_user_ids

    def _inverse_is_favorite(self):
        for rec in self:
            command = (4, self.env.uid) if rec.is_favorite else (3, self.env.uid)
            rec.sudo().favorite_user_ids = [command]

    def _search_is_favorite(self, operator, value):
        """Without this the "My favourites" filter raises: the field is
        computed and not stored, so there is no column to search."""
        if operator not in ("=", "!="):
            raise UserError(_("Favourites can only be filtered as yes or no."))
        wants_favorites = (operator == "=") == bool(value)
        return [("favorite_user_ids", "in" if wants_favorites else "not in",
                 [self.env.uid])]

    def _compute_version_count(self):
        data = self.env["ai.dashboard.version"].sudo()._read_group(
            [("dashboard_id", "in", self.ids)],
            groupby=["dashboard_id"], aggregates=["__count"])
        counts = {d.id: n for d, n in data}
        for rec in self:
            rec.version_count = counts.get(rec.id, 0)

    @api.depends("last_render_ms")
    def _compute_is_slow(self):
        threshold = int(self.env["ir.config_parameter"].sudo().get_param(
            "ai_dashboards_free.slow_ms", "4000"))
        for rec in self:
            rec.is_slow = bool(rec.last_render_ms and
                               rec.last_render_ms > threshold)

    @api.depends("pinned_menu_id")
    def _compute_is_pinned(self):
        for rec in self:
            rec.is_pinned = bool(rec.pinned_menu_id)

    @api.depends("spec_json")
    def _compute_explanation(self):
        for rec in self:
            try:
                rec.explanation = spec_lib.describe(rec.spec(), rec.env)
            except Exception:  # noqa: BLE001 - an unreadable spec still renders
                rec.explanation = _("This dashboard's definition could not be "
                                    "read. Open History to restore an earlier "
                                    "version.")

    # ---------------------------------------------------------------- access
    def spec(self):
        """The parsed specification. Never returns something unvalidated."""
        self.ensure_one()
        try:
            return json.loads(self.spec_json or "{}")
        except ValueError:
            return {}

    def _check_owner(self, action=None):
        """Sharing lets people *see* a dashboard, never edit it.

        Without this, one person's edit silently rewrites what a whole group
        looks at every morning. Editing stays with the owner (and admins).

        ``action`` defaults inside the body rather than in the signature: a
        default argument is evaluated once, when the class is defined, and at
        that moment there is no environment and no language. Odoo notices and
        logs a stack trace on every module load — and the string would be
        frozen in whatever language import time happened to have, so it would
        never translate for anyone.
        """
        action = action or _("change")
        if self.env.su or self.env.user.has_group(GROUP_ADMIN):
            return
        for rec in self:
            if rec.owner_id.id != self.env.uid:
                raise AccessError(_(
                    "\"%(name)s\" belongs to %(owner)s, so only they can "
                    "%(action)s it. You can duplicate it and change your copy.",
                    name=rec.name, owner=rec.owner_id.name, action=action))

    # ----------------------------------------------------------- the quota
    # One draft being worked on and one live dashboard, per person. Counted
    # per owner rather than per database on purpose: a whole team has to be
    # able to try this, or the free edition is a demo rather than the front
    # door to the paid one. The pressure arrives the moment somebody wants a
    # second dashboard, which is exactly when they have decided it works.
    MAX_PER_STATE = 1

    def _quota_message(self, state):
        if state == "draft":
            return _(
                "You already have a draft dashboard. This edition keeps one "
                "draft and one live dashboard per person — publish or discard "
                "the one you have, and this will save. AI Dashboards Pro "
                "removes the limit.")
        return _(
            "You already have a live dashboard. This edition keeps one draft "
            "and one live dashboard per person. Archive the one you have to "
            "publish this, or upgrade to AI Dashboards Pro for as many as you "
            "like.")

    def _check_quota(self, owner, state, exclude=None):
        """Refuse a second dashboard in the same state for the same owner.

        Counted with sudo() and active_test=False: a person must not be able
        to slip past the limit because the other dashboard is archived or
        because a record rule happens to hide it from them. An archived
        dashboard is still theirs and still restorable.
        """
        used = self.sudo().with_context(active_test=False).search_count([
            ("owner_id", "=", owner.id),
            ("state", "=", state),
            ("id", "not in", (exclude or self.browse()).ids),
        ])
        if used >= self.MAX_PER_STATE:
            raise ValidationError(self._quota_message(state))

    # ----------------------------------------------------------- persistence
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["spec_json"] = self._validated_json(vals.get("spec_json"))
        records = super().create(vals_list)
        # After super(), so owner_id and state carry their defaults rather
        # than being guessed from vals - a create that omits either would
        # otherwise skip the check entirely.
        for rec in records:
            rec._check_quota(rec.owner_id, rec.state, exclude=rec)
        records._snapshot(_("Created"))
        return records

    def write(self, vals):
        # Pulled out before super(): it is a message for the history, not a
        # field, and the ORM would refuse it.
        note = vals.pop("_version_note", None)
        spec_changed = "spec_json" in vals
        if spec_changed:
            self._check_owner(_("edit"))
            vals["spec_json"] = self._validated_json(vals["spec_json"])
        if "owner_id" in vals:
            self._check_owner(_("hand over"))
        result = super().write(vals)
        # Checked after the write so the record reads its own new state, which
        # keeps one implementation covering action_publish, a direct write and
        # an owner hand-over alike.
        if {"state", "owner_id"} & set(vals):
            for rec in self:
                rec._check_quota(rec.owner_id, rec.state, exclude=rec)
        if spec_changed:
            self._snapshot(note or _("Edited"))
        return result

    def unlink(self):
        self._check_owner(_("delete"))
        for rec in self:
            if rec.pinned_menu_id:
                rec.pinned_menu_id.sudo().unlink()
        return super().unlink()

    def _validated_json(self, raw):
        """Nothing reaches the column without passing the validator.

        Centralised here rather than in the MCP tool so a spec cannot enter
        through the ORM, a data file or an import and skip the checks.
        """
        if isinstance(raw, str):
            try:
                payload = json.loads(raw or "{}")
            except ValueError:
                raise spec_lib.SpecError(_(
                    "The dashboard specification is not valid JSON."))
        else:
            payload = raw or {}
        validated = spec_lib.validate(payload, self.env, self._scope())
        return json.dumps(validated, sort_keys=True, indent=1)

    @api.model
    def _scope(self):
        """The MCP governance scope that gates what may be built over.

        Authorship is gated here; *viewing* is gated by the viewer's own access
        rights at render time. Keeping those separate is what lets one person
        build a dashboard that shows a colleague their own figures.
        """
        user = self.env.user
        if not user or self.env.su:
            return self.env["mcp.scope"].browse()
        return user.sudo().mcp_effective_scope()

    def _snapshot(self, note):
        """Record every version. Specs are small; keeping all of them is free
        and an AI that can edit your reports needs an undo."""
        self.env["ai.dashboard.version"].sudo().create([{
            "dashboard_id": rec.id,
            "spec_json": rec.spec_json,
            "author_id": self.env.uid,
            "note": note,
        } for rec in self])

    # -------------------------------------------------------------- actions
    def action_publish(self):
        """Promote a draft onto the app tile."""
        self._check_owner(_("publish"))
        self.write({"state": "published"})
        return self.action_open()

    def action_discard(self):
        """Throw a draft away. Live dashboards are archived instead, so a
        shared one never vanishes from under a colleague."""
        self._check_owner(_("discard"))
        drafts = self.filtered(lambda d: d.state == "draft")
        published = self - drafts
        published.write({"active": False})
        drafts.unlink()
        return {"type": "ir.actions.act_window_close"}

    def action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "ai.dashboard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("History of %s") % self.name,
            "res_model": "ai.dashboard.version",
            "view_mode": "list,form",
            "domain": [("dashboard_id", "=", self.id)],
            "target": "current",
        }

    def action_toggle_favorite(self):
        for rec in self:
            rec.is_favorite = not rec.is_favorite

    def action_duplicate(self):
        """Copy someone else's dashboard so you can change your own version."""
        self.ensure_one()
        copy = self.sudo().copy({
            "name": self._free_name(_("%s (copy)") % self.name),
            "owner_id": self.env.uid,
            "state": "draft",
            "pinned_menu_id": False,
        })
        return copy.action_open()

    def _free_name(self, wanted):
        """A name this owner is not already using.

        Two dashboards may share a name - there is deliberately no unique
        constraint, because previewing "P&L" twice while iterating is the most
        ordinary thing a person does here and a database error would be a
        terrible answer to it. But a *copy* should still be findable, so this
        numbers them.
        """
        taken = set(self.sudo().search([
            ("owner_id", "=", self.env.uid)]).mapped("name"))
        if wanted not in taken:
            return wanted
        for n in range(2, 100):
            candidate = "%s %s" % (wanted, n)
            if candidate not in taken:
                return candidate
        return wanted

    # ------------------------------------------------------------ pin to menu
    def action_pin_to_menu(self):
        """Promote a dashboard to a real top-level menu item.

        The one place in this module that uses elevated rights, and it is a
        deliberate administrator action rather than something an assistant can
        trigger. ir.ui.menu.create clears the menu cache itself
        (ir_ui_menu.py:152), so the item appears without a restart - though an
        already-open browser still needs a reload to see it.
        """
        self.ensure_one()
        if not self.env.user.has_group(GROUP_ADMIN):
            raise AccessError(_(
                "Only an AI Dashboards administrator can add something to the "
                "main menu."))
        if self.state != "published":
            raise UserError(_("Save this dashboard before pinning it."))
        if self.pinned_menu_id:
            return self.action_open()

        action = self.env["ir.actions.act_window"].sudo().create({
            "name": self.name,
            "res_model": "ai.dashboard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        })
        menu = self.env["ir.ui.menu"].sudo().create({
            "name": self.name,
            "parent_id": self.env.ref("ai_dashboards_free.menu_dashboards_root").id,
            "action": "ir.actions.act_window,%s" % action.id,
            "sequence": 50,
            # No group restriction: a pinned dashboard is one an administrator
            # deliberately promoted, and the record rule underneath still keeps
            # the dashboard itself to its owner.
        })
        self.sudo().pinned_menu_id = menu.id
        _logger.info("AI Dashboards: %s pinned '%s' to the menu",
                     self.env.user.login, self.name)
        return self.action_open()

    def action_unpin(self):
        self.ensure_one()
        if not self.env.user.has_group(GROUP_ADMIN):
            raise AccessError(_("Only an AI Dashboards administrator can do that."))
        if self.pinned_menu_id:
            self.pinned_menu_id.sudo().unlink()
        return self.action_open()

    # ------------------------------------------------------------ portability
    def action_export_spec(self):
        """The spec is the portable unit: build a P&L once, install it for
        thirty clients."""
        self.ensure_one()
        return {
            "name": self.name,
            "description": self.description or "",
            "spec": self.spec(),
        }

    @api.model
    def action_import_spec(self, payload):
        payload = payload or {}
        return self.create({
            "name": payload.get("name") or _("Imported dashboard"),
            "description": payload.get("description") or "",
            "spec_json": json.dumps(payload.get("spec") or {}),
            "state": "draft",
        }).id

    # ------------------------------------------------------------- notifying
    def _notify_ready(self, headline=None):
        """Tell an open Odoo tab that a dashboard has arrived.

        The moment this exists to fix: you ask Claude for a dashboard, switch
        to Odoo, and have no idea whether it worked. res.partner inherits
        bus.listener.mixin, so this is the safe channel API rather than a
        guessable string channel.
        """
        for rec in self:
            rec.owner_id.partner_id._bus_send("ai_dashboards_free.ready", {
                "id": rec.id,
                "name": rec.name,
                "state": rec.state,
                "headline": headline or _("\"%s\" is ready.") % rec.name,
            })
