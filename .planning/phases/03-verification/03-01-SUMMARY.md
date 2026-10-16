---
phase: 03-verification
plan: 01
subsystem: testing
tags: [audit-instrumentation, text-cleaning, corpus-sampler, build-summary, pytest, ruff]

# Dependency graph
requires:
  - phase: 01-cleaning
    provides: clean_text single choke point and idempotent writer gate the audit delegates to
  - phase: 02-source-hardening
    provides: URL/email strip steps whose removals are now counted via subn
provides:
  - audit_clean() + AuditCounts as the single cleaning implementation
  - per-genre/global audit_rates flowing from writer summary into build_summary.json
  - tests/test_verification.py pinning exact rate arithmetic
affects: [03-02 full-tier gate, verify-work acceptance signal]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 3406
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns: [audit-counter NamedTuple beside cleaner, choke-point-only accumulation, input-honest rate denominator]

key-files:
  created: [tests/test_verification.py]
  modified: [src/polish_corpus/text_cleaning.py, src/polish_corpus/corpus_sampler.py, src/polish_corpus/builder.py]

key-decisions:
  - "_drop_token delegates to _drop_cause so digit/foreign classification has one implementation"
  - "Empty-after-clean docs record drops but consume no quota, keeping rates input-honest"
  - "audit_rates emitted both nested in summary and top-level in build_summary.json"

patterns-established:
  - "Rate denominator is dropped_total + tokens_kept (shares of raw input tokens)"
  - "URL/email reported as counts only, never rates (they vanish before tokenization)"
  - "paradigm_docs_excluded: true marks dictionary-derived docs as out of audit scope"

requirements-completed: [VER-03]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "audit_clean() + AuditCounts with clean_text delegating (zero behavior change)"
    requirement: "VER-03"
    verification:
      - kind: unit
        ref: "tests/test_verification.py#test_clean_text_delegates_to_audit_clean"
        status: pass
      - kind: integration
        ref: "pytest tests/test_smoke.py -q (quick-test build, no behavior drift)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Per-genre/global audit_rates from writer choke point into build_summary.json"
    requirement: "VER-03"
    verification:
      - kind: unit
        ref: "tests/test_verification.py#test_audit_rates_exact_arithmetic"
        status: pass
      - kind: unit
        ref: "tests/test_verification.py#test_sizing_path_does_not_double_count"
        status: pass
      - kind: unit
        ref: "tests/test_verification.py#test_empty_after_clean_records_drops_without_quota"
        status: pass
      - kind: integration
        ref: "quick-test build_summary.json contains audit_rates (global + per-genre)"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-10-16
status: complete
---

# Phase 03 Plan 01: Audit-Rate Tracer Summary

**Input-honest audit rates flowing from the `add_document` choke point to `build_summary.json`, via `audit_clean()` + `AuditCounts` with `clean_text` as pure delegation**

## Performance

- **Duration:** 25 min
- **Started:** 2026-10-16T07:30:00Z
- **Completed:** 2026-10-16T07:55:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `audit_clean()` in `text_cleaning.py` returns `(cleaned, AuditCounts)` from the same single pass; `clean_text()` is now `return audit_clean(text)[0]` with zero behavior change (full suite green)
- `BalancedCorpusWriter` accumulates per-genre audit counters ONLY in `add_document()` and exposes `audit_rates` (global + per-genre, `paradigm_docs_excluded: true`) from `summary()`
- `build_summary.json` carries top-level `audit_rates` verbatim from the writer summary; quick-test build proves it end-to-end (global: 64 digit drops / 5708 kept from seed numbering)
- New `tests/test_verification.py` with 12 tests: exact arithmetic, no sizing-path double count, empty-after-clean accounting, delegation equivalence battery

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end audit rates — audit_clean through writer to build_summary.json** - `b661db7` (feat)
2. **Task 2: Rate-arithmetic regression tests** - `d783187` (test)

## Files Created/Modified

- `src/polish_corpus/text_cleaning.py` - `AuditCounts` NamedTuple, `_drop_cause()` classifier, `audit_clean()`, `clean_text()` as delegation
- `src/polish_corpus/corpus_sampler.py` - per-genre `audit_counts`, choke-point-only accumulation, `_audit_rate_entry()` helper, `audit_rates` in `summary()`
- `src/polish_corpus/builder.py` - top-level `"audit_rates"` key in `build_summary.json`
- `tests/test_verification.py` - 12 regression tests for rate arithmetic and delegation

## Decisions Made

- `_drop_token()` now delegates to `_drop_cause()` (digit-first order preserved verbatim) so the keep/drop predicate and the audit classifier cannot drift apart; behavior identical, verified by the unchanged full suite
- Empty-after-clean docs record their drops in `audit_counts` but still return `""` without consuming a doc slot — drops were real input, so rates stay input-honest
- `audit_rates` emitted both nested inside `summary` and as a top-level `build_summary.json` key, so the 03-02 gate script can read it directly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed duplicated `from typing import NamedTuple` import**
- **Found during:** Task 2 (Rate-arithmetic regression tests)
- **Issue:** `ruff check` reported I001 — the import line appeared twice in `text_cleaning.py`
- **Fix:** Deleted one duplicate line
- **Files modified:** src/polish_corpus/text_cleaning.py
- **Verification:** `ruff check src/ tests/` passes; full suite re-run green
- **Committed in:** d783187 (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial lint fix, no behavior or scope impact.

## Issues Encountered

- System-python lacks `pyarrow`, so the smoke quick-test was skipped there; re-ran everything under `.venv/bin/python` (pyarrow 26.0.0), where all 4 smoke tests pass including the real quick-test build
- Commits landed on `master`: project config sets `git.branching_strategy: "none"` and prior phase commits (`83f90f7`, `d26b965`, `990c205`) are all on master, so master commits are the established repo convention; task files were staged individually, orchestrator-owned `.planning/` modifications left untouched

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 acceptance signal is live: every build (including the 03-02 compact gate) now reports `foreign_fragment_rate`, `digit_token_rate`, and per-genre rates
- 03-02 can cross-check script-measured rates against writer-reported rates exactly; denominator semantics (`dropped_total + tokens_kept`) are pinned by test

## Self-Check: PASSED

- `audit_clean`/`audit_rates` code paths verified by 12 new tests + quick-test build emitting the key
- Commits `b661db7`, `d783187` both ancestors of HEAD

---
*Phase: 03-verification*
*Completed: 2026-10-16*
