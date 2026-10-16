---
phase: 01-cleaning-stage-shared-tokenizer
review: 01-REVIEW.md
review_status: issues_found
dispositioned: 2026-10-16T20:30:00Z
open: 0
---

# Phase 01: Code Review Disposition

Review `01-REVIEW.md` reported 8 findings (1 critical, 4 warning, 3 info).
All Critical + Warning findings were fixed before verification; Info findings
required no action by design. Ledger below records what happened to each one.

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | fix commit `0ccc2e5` — clean_text reordered to NFC → unescape → NFC → strip → filter; `_drop_token` kills tokens on any M-category char; repro `cafe&#769;` now yields `['słowo', 'inne']` (verified by orchestrator re-execution) |
| WR-01 | warning | fixed | fix commit `0ccc2e5` (shared ordering block with CR-01) — strip runs after unescape; `clean_text("słowo &#0; inne") == "słowo inne"` |
| WR-02 | warning | fixed | fix commit `824b940` — TOKEN_RE allows repeated hyphen groups `(?:-...)*`; triple compound tokenizes whole and agrees with `is_valid_token` |
| WR-03 | warning | fixed | fix commit `6adda97` — `chunk_text_stream` cleans before counting; foreign-only paragraph skipped |
| WR-04 | warning | fixed | fix commit `9a8ad54` — `add_document` returns `""` sentinel on empty-after-clean (no write, no counters, no quota consumption); test updated to `test_empty-after-clean_skips_write_and_quota` |
| IN-01 | info | skipped | No action required — cosmetic typing note, no defect |
| IN-02 | info | skipped | No action required — paradigm-path bypass is documented design, plan-scoped out |
| IN-03 | info | skipped | No action required — accepted residual per threat disposition T-01-02 (single-pass decode) |

Post-fix gates: `pytest tests/ -q` → 47 passed, 1 skipped; `ruff check src/ tests/` → clean.
