# -*- coding: utf-8 -*-
"""Who can see, build and change a dashboard.

Sharing on this model means *sight*, never edit. That distinction is the one
worth testing hardest: without it, one person's change silently rewrites what a
whole team looks at every morning, and nobody finds out until the numbers are
wrong in a meeting.
"""
import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .test_spec import minimal


@tagged("post_install", "-at_install")
class TestDashboardAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alice = cls.env["res.users"].create({
            "name": "Alice", "login": "ai_dash_alice",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.bob = cls.env["res.users"].create({
            "name": "Bob", "login": "ai_dash_bob",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.team = cls.env["res.groups"].create({"name": "TEST dashboard team"})
        cls.admin = cls.env["res.users"].create({
            "name": "Dash Admin", "login": "ai_dash_admin",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("ai_dashboards_free.group_dashboard_admin").id])],
        })

    def _dashboard(self, user, **vals):
        values = {
            "name": vals.pop("name", "Alice's board"),
            "spec_json": json.dumps(minimal()),
            "state": "published",
        }
        values.update(vals)
        return self.env["ai.dashboard"].with_user(user).create(values)

    # ------------------------------------------------------------- the grant
    def test_every_mcp_user_can_build_dashboards(self):
        """Same reasoning as the MCP User role: navigation, not authority."""
        self.assertTrue(self.alice.has_group(
            "ai_dashboards_free.group_dashboard_user"))

    def test_an_employee_is_not_made_an_administrator(self):
        self.assertFalse(self.alice.has_group(
            "ai_dashboards_free.group_dashboard_admin"))

    # ---------------------------------------------------------- own vs others
    def test_a_private_dashboard_is_invisible_to_others(self):
        board = self._dashboard(self.alice)
        found = self.env["ai.dashboard"].with_user(self.bob).search(
            [("id", "=", board.id)])
        self.assertFalse(found, "a private dashboard must not be readable")

    def test_a_colleague_still_cannot_see_it_after_a_group_is_shared_with(self):
        """Sharing is a Pro feature, so there is no route to widen the rule.

        The record rule has nothing but owner_id in its domain, and neither
        share field exists on the model any more - so this is the shape of the
        whole permission model in this edition, not one case of it.
        """
        self.bob.write({"group_ids": [(4, self.team.id)]})
        board = self._dashboard(self.alice)
        self.assertFalse(self.env["ai.dashboard"].with_user(self.bob).search(
            [("id", "=", board.id)]))

    def test_the_share_fields_are_gone_rather_than_merely_hidden(self):
        fields = self.env["ai.dashboard"]._fields
        for name in ("share_user_ids", "group_ids", "is_shared",
                     "subscription_ids", "is_subscribed"):
            self.assertNotIn(name, fields, "%s must not exist here" % name)

    def test_a_colleague_can_duplicate_and_own_the_copy(self):
        """Duplicating someone else's is how you work from it without sharing.

        Only reachable for an administrator here, who can see every dashboard;
        an ordinary colleague cannot resolve one they do not own.
        """
        board = self._dashboard(self.alice)
        board.with_user(self.admin).action_duplicate()
        copy = self.env["ai.dashboard"].sudo().search(
            [("owner_id", "=", self.admin.id)], limit=1)
        self.assertTrue(copy)
        self.assertEqual(copy.state, "draft")

    def test_only_an_owner_may_delete(self):
        board = self._dashboard(self.alice)
        with self.assertRaises(AccessError):
            board.with_user(self.bob).unlink()

    # ------------------------------------------------------------- pinning
    def test_pinning_is_administrator_only(self):
        board = self._dashboard(self.alice)
        with self.assertRaises(AccessError):
            board.with_user(self.alice).action_pin_to_menu()

    def test_translations_are_not_frozen_at_import(self):
        """A default argument is evaluated once, when the class is defined —
        with no environment and no language. Odoo logs a stack trace for it on
        every module load, and the string would never translate for anyone."""
        import inspect
        from ..models import ai_dashboard, ai_dashboard_render
        from ..models import ai_dashboard_spec
        for module in (ai_dashboard, ai_dashboard_render, ai_dashboard_spec):
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ != module.__name__:
                    continue
                for meth_name, meth in inspect.getmembers(
                        obj, inspect.isfunction):
                    defaults = inspect.signature(meth).parameters
                    for pname, param in defaults.items():
                        default = param.default
                        if default is inspect.Parameter.empty:
                            continue
                        self.assertNotIn(
                            type(default).__name__, ("LazyTranslate", "lazy"),
                            "%s.%s has a translated default for '%s' — resolve "
                            "it inside the body instead"
                            % (obj.__name__, meth_name, pname))
