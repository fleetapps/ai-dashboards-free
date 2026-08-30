# -*- coding: utf-8 -*-
"""The MCP tools, and the governance they inherit.

The most important tests here are the two seams with AI MCP. A writing handler
left out of mcp.tool._write_handlers() computes writes=False and slips past
every gate built on that flag; and AI MCP refuses writing verbs outright, so
this module has to be the declared exception for its own three - and only its
own three. Get either wrong and the product is either unsafe or does nothing.
"""
import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from ..models.mcp_engine import (
    DASHBOARD_READ_HANDLERS,
    DASHBOARD_WRITE_HANDLERS,
)
from .test_spec import minimal


@tagged("post_install", "-at_install")
class TestDashboardTools(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Engine = cls.env["mcp.engine"]
        cls.partner_model = cls.env["ir.model"]._get("res.partner")
        cls.user = cls.env["res.users"].create({
            "name": "Tools User", "login": "ai_dash_tools",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.scope = cls.env["mcp.scope"].create({
            "name": "TEST dashboard tools",
            "line_ids": [(0, 0, {"model_id": cls.partner_model.id,
                                 "can_read": True})],
        })

    def _call(self, name, args, scope=None, user=None):
        return self.Engine.with_user(user or self.env.user).call_tool(
            scope or self.scope, name, args, {})

    def _payload(self, result):
        return json.loads(result["content"][0]["text"])

    # ------------------------------------------------------- classification
    def test_write_tools_are_registered_as_writing(self):
        Tool = self.env["mcp.tool"]
        for handler in DASHBOARD_WRITE_HANDLERS:
            self.assertIn(handler, Tool._write_handlers(),
                          "%s writes and must be registered" % handler)

    def test_read_tools_are_not_registered_as_writing(self):
        Tool = self.env["mcp.tool"]
        for handler in DASHBOARD_READ_HANDLERS:
            self.assertNotIn(handler, Tool._write_handlers())

    def test_write_tools_are_advertised_and_gated_at_the_call(self):
        """AI MCP has no read-only kill switch to hide them behind.

        That edition implements no writing verb at all, so it drops the
        scope-level switch and refuses writers in _check_write_permitted
        instead. Which means these tools are listed - deliberately, since a
        tool a client cannot see is one it can never be told to ask permission
        for - and the guard is what decides. TestWriteGuardIntegration below
        covers the decision itself.
        """
        names = {t["name"] for t in self.Engine.list_tools(self.scope)}
        self.assertIn("get_dashboard_schema", names)
        self.assertIn("save_dashboard", names)
        self.assertNotIn("read_only", self.env["mcp.scope"]._fields,
                         "if this comes back, hide write tools again")

    def test_write_tools_carry_the_right_annotations(self):
        tools = {t["name"]: t["annotations"]
                 for t in self.Engine.list_tools(self.scope)}
        self.assertTrue(tools["get_dashboard_schema"]["readOnlyHint"])
        self.assertFalse(tools["save_dashboard"]["readOnlyHint"])
        self.assertTrue(tools["delete_dashboard"]["destructiveHint"])

    def test_no_tool_can_reach_a_server_action(self):
        """ir.actions.server runs safe_eval(code, mode='exec'). Write access
        there is remote code execution, so it must be unreachable."""
        for tool in self.Engine.list_tools(self.scope):
            schema = json.dumps(tool.get("inputSchema", {}))
            self.assertNotIn("ir.actions.server", schema)
            self.assertNotIn("ir.actions.server", tool["description"])

    # ------------------------------------------------------------ discovery
    def test_the_schema_tool_teaches_the_format(self):
        payload = self._payload(self._call("get_dashboard_schema", {}))
        self.assertIn("widget_types", payload)
        self.assertIn("example", payload)
        self.assertIn("kpi", payload["widget_types"])

    def test_the_schema_example_is_itself_valid(self):
        """A worked example a model copies has to actually validate, or the
        first thing it does is get refused."""
        from ..models import ai_dashboard_spec as spec_lib
        example = self._payload(self._call("get_dashboard_schema", {}))["example"]
        spec_lib.validate(example)  # structure only; sale.order may be absent

    def test_seed_from_view_suggests_real_fields(self):
        payload = self._payload(
            self._call("seed_from_view", {"model": "res.partner"}))
        self.assertTrue(payload["suggested_group_by"])
        self.assertEqual(payload["model"], "res.partner")

    def test_seed_refuses_a_model_outside_the_scope(self):
        result = self._call("seed_from_view", {"model": "res.users"})
        self.assertTrue(result["isError"])

    # -------------------------------------------------------------- writing
    def test_preview_creates_a_draft_and_samples_the_figures(self):
        payload = self._payload(
            self._call("preview_dashboard", {"spec": minimal()}))
        self.assertEqual(payload["state"], "draft")
        self.assertTrue(payload["url"].endswith(str(payload["dashboard_id"])))
        self.assertIsInstance(payload["sample"], list)
        board = self.env["ai.dashboard"].browse(payload["dashboard_id"])
        self.assertEqual(board.state, "draft")
        self.assertTrue(board.built_by_ai)

    def test_a_preview_does_not_reach_the_app_tile(self):
        payload = self._payload(
            self._call("preview_dashboard", {"spec": minimal()}))
        published = self.env["ai.dashboard"].search(
            [("id", "=", payload["dashboard_id"]), ("state", "=", "published")])
        self.assertFalse(published)

    def test_save_publishes(self):
        payload = self._payload(
            self._call("save_dashboard", {"spec": minimal(), "name": "Saved"}))
        board = self.env["ai.dashboard"].browse(payload["dashboard_id"])
        self.assertEqual(board.state, "published")
        self.assertEqual(board.name, "Saved")

    def test_save_can_publish_an_existing_preview(self):
        preview = self._payload(
            self._call("preview_dashboard", {"spec": minimal()}))
        self._call("save_dashboard",
                   {"dashboard_id": preview["dashboard_id"]})
        board = self.env["ai.dashboard"].browse(preview["dashboard_id"])
        self.assertEqual(board.state, "published")

    def test_an_invalid_spec_comes_back_as_a_usable_error(self):
        """The correction loop: the model has to be able to act on this."""
        bad = minimal()
        bad["widgets"][0]["query"]["measures"] = ["name:sum"]
        result = self._call("preview_dashboard", {"spec": bad})
        self.assertTrue(result["isError"])
        self.assertIn("numeric", self._payload(result)["message"])

    def test_a_missing_spec_points_at_the_schema_tool(self):
        result = self._call("preview_dashboard", {})
        self.assertTrue(result["isError"])
        self.assertIn("get_dashboard_schema", self._payload(result)["message"])

    def test_get_dashboard_returns_the_spec_for_editing(self):
        created = self._payload(
            self._call("save_dashboard", {"spec": minimal()}))
        payload = self._payload(self._call(
            "get_dashboard", {"dashboard_id": created["dashboard_id"]}))
        self.assertEqual(payload["spec"]["schema"], minimal()["schema"])
        self.assertTrue(payload["explanation"])

    def test_deleting_someone_elses_dashboard_is_refused(self):
        board = self.env["ai.dashboard"].with_user(self.user).create({
            "name": "Theirs", "spec_json": json.dumps(minimal()),
            "state": "published",
        })
        result = self._call("delete_dashboard", {"dashboard_id": board.id})
        self.assertTrue(result["isError"])

    def test_every_call_is_audited(self):
        before = self.env["mcp.audit.log"].search_count([])
        self._call("get_dashboard_schema", {})
        self.assertEqual(self.env["mcp.audit.log"].search_count([]), before + 1)

    # ------------------------------------------------------ preview samples
    def test_the_preview_sample_reports_every_widget_type(self):
        """A summary that only looked for `series` and `value` told the model
        its pivot was empty — and the likeliest response to that is "fixing" a
        dashboard that was working."""
        spec = minimal()
        spec["widgets"] = [
            {"id": "k", "type": "kpi", "title": "Count", "span": 3,
             "query": {"model": "res.partner", "measures": ["__count"]}},
            {"id": "b", "type": "bar", "title": "By country", "span": 6,
             "query": {"model": "res.partner", "group_by": ["country_id"],
                       "measures": ["__count"]}},
            {"id": "t", "type": "table", "title": "Rows", "span": 12,
             "query": {"model": "res.partner", "group_by": ["is_company"],
                       "measures": ["__count"]}},
            {"id": "p", "type": "pivot", "title": "Grid", "span": 12,
             "query": {"model": "res.partner",
                       "group_by": ["country_id", "is_company"],
                       "measures": ["__count"]}},
        ]
        sample = self.env["ai.dashboard.render"].sample(spec, limit=4)
        by_id = {row["type"]: row for row in sample}

        self.assertIn("value", by_id["kpi"])
        self.assertIn("series", by_id["bar"])
        self.assertIn("sample_rows", by_id["table"])
        # The pivot must describe itself rather than looking empty.
        pivot = by_id["pivot"]
        self.assertIn("rows_shown", pivot)
        self.assertIn("grand_total", pivot)
        self.assertNotIn("series", pivot,
                         "a pivot reporting an empty series reads as broken")

    def test_a_sample_distinguishes_empty_from_broken(self):
        spec = minimal()
        spec["widgets"] = [{
            "id": "e", "type": "kpi", "title": "None", "span": 3,
            "query": {"model": "res.partner", "measures": ["__count"],
                      "domain": [["name", "=", "nothing at all here"]]},
        }]
        row = self.env["ai.dashboard.render"].sample(spec)[0]
        self.assertNotIn("error", row, "an empty result is not an error")


@tagged("post_install", "-at_install")
class TestWriteGuardIntegration(TransactionCase):
    """AI MCP refuses every writing verb; this module has to be the exception.

    Without the _check_write_permitted override, save_dashboard and
    delete_dashboard are refused at the door and the entire product - "ask
    Claude for a dashboard" - does nothing but list. This is the one seam
    between the two free modules, so it gets a test rather than a comment.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env["mcp.engine"]
        cls.Tool = cls.env["mcp.tool"]

    def test_dashboard_write_verbs_are_permitted(self):
        for name in ("preview_dashboard", "save_dashboard", "delete_dashboard"):
            tool = self.Tool.search([("name", "=", name)], limit=1)
            self.assertTrue(tool, "%s must be registered" % name)
            self.assertTrue(tool.writes, "%s must be classified as writing" % name)
            self.engine._check_write_permitted(tool, {})   # must not raise

    def test_a_foreign_writing_verb_is_still_refused(self):
        """The exemption is for this module's verbs, not for writing at all."""
        class ForeignTool:
            name = "wreck_everything"
            handler = "unlink_record"
            writes = True

        with self.assertRaises(AccessError):
            self.engine._check_write_permitted(ForeignTool(), {})
