# AI Dashboards Free (Odoo 19)

Ask your own AI assistant for a dashboard. Get a real one in Odoo.

Connect Claude, ChatGPT or Cursor once, describe the dashboard you want in
plain English, and it lands in Odoo as a screen you open like any other.

## The AI never writes code

It writes a **specification** — which model, which filter, which grouping,
which measures — and Odoo validates it and draws the charts. There is no
generated SQL anywhere in this module. That matters more than it sounds: SQL
written by a language model runs outside the ORM, and therefore outside every
access right and record rule your database has. A specification cannot, because
it is data rather than instructions.

## Dashboards store the question, not the answer

A saved dashboard holds *"revenue by month, this year"* — never the numbers.
The query runs when you open it, **as you**, through the ORM. Never stale,
never someone else's figures, multi-company boundaries respected without
anyone configuring anything.

## What this edition does not do

| | Free | Pro |
|---|---|---|
| Dashboards | 1 draft + 1 live, per person | Unlimited |
| Sharing with people or teams | — | ✓ |
| Scheduled email | — | ✓ |
| Preview, drill-through, versions, pivots, comparison | ✓ | ✓ |
| Build and edit by chatting | ✓ | ✓ |

The limit is per person, not per database — a whole team can try it.

## Requires

[AI MCP](https://github.com/fleetapps/ai-mcp) (`ai_mcp`), which provides the
connection, the governance scope and the audit trail. Dashboard tools appear on
the MCP connection you already have — one URL, one sign-in, one log.

Odoo 19, Community or Enterprise.

## Licence

LGPL-3. See [LICENSE](LICENSE).
