# -*- coding: utf-8 -*-
# Manifest reference:
# https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html
{
    "name": "AI Dashboards Free",
    "version": "19.0.1.0.0",
    "category": "Productivity/Dashboard",
    "summary": "Build Odoo dashboards by chatting with Claude, ChatGPT or any "
               "MCP client — then open them in Odoo like any other app. No API "
               "key, no generated SQL, every query runs as the person looking.",
    "description": """
AI Dashboards Free
==================

Ask your own AI assistant for a dashboard. Get a real one in Odoo.

You already pay for Claude or ChatGPT. Connect it once, describe the dashboard
you want in plain English, and it lands in Odoo as a screen you open like any
other.

The AI never writes code
------------------------
It writes a **specification** - which model, which filter, which grouping,
which measures - and Odoo validates it and draws the charts. There is no
generated SQL anywhere in this module, which matters more than it sounds: SQL
written by a language model runs outside the ORM and therefore outside every
access right and record rule your database has. A specification cannot do
that, because it is data rather than instructions.

Dashboards store the question, not the answer
---------------------------------------------
A saved dashboard holds *"revenue by month, this year"* - never the numbers.
The query runs when you open it, **as you**, through the ORM. So it is never
stale, and it respects multi-company boundaries without anyone configuring it.

What you get
------------
* **Preview before it is saved.** Nothing is kept until you have looked at it.
* **Drill through.** Click a bar, get the records behind it in a normal list.
* **Edit by conversation.** Ask for a change; the assistant reads what exists
  and proposes a diff instead of rebuilding from scratch.
* **A light editor.** Drag to reorder, resize, rename, recolour - without going
  back to the chat for small things.
* **Every version kept.** One-click revert when a change was wrong.
* **Compare against last year** - or the previous period - across the whole
  dashboard at once.
* **Pivot tables** over two dimensions, with both axes paged independently.
* **It explains itself.** A plain-English account of exactly which data each
  dashboard reads and whose permissions it runs under.

What this edition does not do
-----------------------------
* **One draft and one live dashboard per person.** Enough to build something
  real and use it every day; the ceiling arrives when you want a second.
* **No sharing.** A dashboard is private to the person who made it.
* **No scheduled email.** Nothing is sent on a timer.

`AI Dashboards Pro` lifts all three: unlimited dashboards, sharing with people
and whole teams, and a weekday/weekly/monthly email that is calculated with
each recipient's own permissions at the moment it is sent.

Requires AI MCP, which provides the connection, the governance scope and the
audit trail. Dashboard tools appear on the connection you already have - one
URL, one sign-in, one log.
""",
    "author": "Fleet",
    "website": "https://fleet.ke",
    "support": "developers@fleet.ke",
    "maintainer": "Fleet",
    "license": "LGPL-3",
    # ai_mcp_free brings the MCP transport, the OAuth 2.1 server, the tool registry
    # and the audit log. `bus` (used to tell an open browser a dashboard is
    # ready) arrives through its `mail` dependency.
    "depends": ["ai_mcp_free"],
    "data": [
        "security/ai_dashboards_free_security.xml",
        "security/ir.model.access.csv",
        "data/mcp_capability_data.xml",
        "views/ai_dashboard_views.xml",
        "views/ai_dashboard_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_dashboards_free/static/src/dashboard/*.scss",
            "ai_dashboards_free/static/src/dashboard/*.js",
            "ai_dashboards_free/static/src/dashboard/*.xml",
        ],
    },
    "pre_init_hook": "pre_init_check",
    "installable": True,
    "application": True,
}
