# Changelog

All notable changes to **AI Dashboards Free** are documented here.

## [19.0.1.0.0] — 2026-08-30

First open-source release. The free edition of AI Dashboards, extracted from
the commercial module and published under LGPL-3.

### Added
- Build and edit dashboards by chatting with any MCP client, through the
  connection `ai_mcp_free` already provides.
- Preview before saving, drill-through to the records behind a bar, full
  version history with one-click revert, a light drag-to-arrange editor,
  period comparison, and two-dimensional pivot tables.
- A plain-English explanation, per dashboard, of exactly which data it reads
  and whose permissions it runs under.

### Notes
- **One draft and one live dashboard per person.** Counted per owner rather
  than per database, so a whole team can evaluate it; archived dashboards still
  count, because archiving is not deleting.
- **No sharing.** A dashboard is private to its owner — the record rule has
  nothing but `owner_id` in it, and the share fields do not exist on the model.
- **No scheduled email.** The subscription model, its cron and its mail
  template are absent rather than disabled.
- All three are lifted by AI Dashboards Pro.
