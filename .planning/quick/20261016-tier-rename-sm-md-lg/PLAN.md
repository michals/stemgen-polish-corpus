---
task: tier-rename-sm-md-lg
date: 2026-10-16
status: in-progress
---

# Quick Task: Rename tiers compact/recommended/extended → sm/md/lg

Rename all three corpus size tier names: `compact` → `sm`, `recommended` → `md`,
`extended` → `lg`. Clean rename, no backward-compat aliases.

Files to change (tier-name references only — prose uses of "recommended"/"extended"
such as "Using uv (recommended)" stay untouched):
- `src/polish_corpus/config.py` — TIERS keys + TierConfig names + docstring example
- `src/polish_corpus/cli.py` — `--tier` default + help text
- `src/polish_corpus/builder.py` — docstring example, `tier_name` default, TIERS fallback
- `tests/test_smoke.py` — tier key asserts, output-dir assert, build tier_name
- `scripts/verify_zero_fragments.py` — `--dist-dir` default `dist/compact` → `dist/sm`
- `README.md` — tier table, usage examples, output-structure paths

Verify: `pytest tests/ -q`, `ruff check src/ tests/ scripts/`,
`--help` shows sm/md/lg choices, quick-test build lands in `dist/md/`.
