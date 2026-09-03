==================
AI Dashboards Free
==================

Ask your own AI assistant for a dashboard. Get a real one in Odoo.

Connect Claude, ChatGPT or Cursor once through `AI MCP`, describe the dashboard
you want in plain English, and it lands in Odoo as a screen you open like any
other.

Installation
============

Drop ``ai_dashboards_free`` into your addons path and install it from Apps.
Odoo installs `AI MCP` (``ai_mcp_free``) alongside it as a dependency — that is what
provides the connection, the governance scope and the audit trail.

Configuration
=============

None. Connect an assistant on :menuselection:`AI MCP --> Connect your AI`, and
the dashboard tools appear on the connection you already have.

Usage
=====

1. Ask your assistant for a dashboard: *"build me a dashboard of revenue by
   month and open orders by salesperson."*
2. It writes a **specification** — model, filter, grouping, measures — which
   Odoo validates and draws. There is no generated SQL anywhere in this module.
3. The result appears as a **draft** under :menuselection:`AI Dashboards`.
   Nothing is kept until you have looked at it.
4. Publish it, and it becomes a live screen you open like any other.

Ask for changes in the same conversation — the assistant reads what exists and
proposes a diff rather than rebuilding. Small cosmetic changes (reorder, resize,
rename, recolour) are quicker in the built-in editor.

What this edition does not do
=============================

* **One draft and one live dashboard per person.** Publish or discard the draft
  you have, or archive the live one, to free the slot.
* **No sharing.** A dashboard is private to the person who made it.
* **No scheduled email.**

All three are lifted by `AI Dashboards Pro`, which adds unlimited dashboards,
sharing with named people and whole teams, and a weekday/weekly/monthly email
calculated with each recipient's own permissions at the moment it is sent.

Why there is no generated SQL
=============================

SQL written by a language model runs outside the ORM, and therefore outside
every access right and record rule your database has. A specification cannot,
because it is data rather than instructions: Odoo validates it against the
permission matrix and the reader's own rights, then executes it through the
ORM as that person.

The consequence worth knowing: a dashboard stores the *question*, never the
answer. It is never stale, and it can never show anyone a row they could not
open themselves.

Bug Tracker
===========

Please report issues to the maintainer at developers@fleet.ke.

Credits
=======

This module is maintained by `Fleet <https://fleet.ke>`_.

Licensed under the GNU Lesser General Public License v3.
