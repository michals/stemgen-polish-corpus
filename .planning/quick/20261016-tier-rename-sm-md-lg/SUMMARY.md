---
task: tier-rename-sm-md-lg
date: 2026-10-16
status: complete
---

# Quick Task Summary: Rename tiers compact/recommended/extended → sm/md/lg

Renamed all three corpus size tiers (`compact`→`sm`, `recommended`→`md`,
`extended`→`lg`). Clean rename, no backward-compat aliases — old `--tier`
values are now rejected by argparse.

Commit: `f0bff69` — 6 files, 35 insertions, 35 deletions.

Verification: `pytest tests/ -q` 113 passed; `ruff check src/ tests/ scripts/`
clean; `--help` shows `--tier {sm,md,lg}`; default output resolves to `dist/md/`.
Prose uses of "recommended"/"extended" (e.g. "Using uv (recommended)") untouched.
Remaining old-tier mentions live only in archived `.planning/` phase artifacts
(plans, summaries, verification reports) — historical record, intentionally frozen.

Follow-up note: existing `dist/compact/` build outputs on disk are stale paths;
the next build writes to `dist/sm|md|lg/`. Consumers passing old `dist/<tier>`
paths (e.g. gate `--dist-dir`, `stemgen build --corpus`) need the new names.
