---
phase: 01-cleaning-stage-shared-tokenizer
plan: 02
subsystem: corpus-pipeline
tags: [text-cleaning, tokenizer, polish, regression-tests, html-entities, numeric-policy]

# Dependency graph
requires:
  - phase: 01-01 tracer cleaning gate
    provides: text_cleaning.py with writer-boundary gate and minimal drop/retain tests
provides:
  - Load-bearing clean_text() ordering pinned by regression tests (NFC-first, unescape-before-filter, filter-before-normalize)
  - Complete audit §2 fixture battery (11 foreign drop-cases, numeric policy, hyphen per-segment validation, empty-after-clean)
affects: [source hardening, audit rates, full-tier rebuild gate]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 1750
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns: [ordering regression pins, audit fixture battery]

key-files:
  created: []
  modified: [src/polish_corpus/text_cleaning.py, tests/test_cleaning.py]

key-decisions:
  - "NFD fixtures written as explicit \\u0301 escapes, not literal combining chars — editor NFC normalization can never silently break the ordering test"
  - "tienne-la validity asserted only through clean_text whole-token drop, not is_valid_token — per-segment validation correctly accepts Polish-only segments; the no-salvage guarantee lives at the clean stage"

patterns-established:
  - "Ordering tests assert post-conditions (entity gone, fragment absent) rather than step internals, so the numbered pipeline comments stay free to evolve"

requirements-completed: [CLN-03, TOK-02]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "Entity/NFD/control ordering pinned — &eacute; decodes then drops, NFD input drops after NFC, controls/FFFD vanish, quotes/dashes normalize without resurrecting dropped tokens"
    requirement: "CLN-03"
    verification:
      - kind: unit
        ref: "tests/test_cleaning.py#test_entity_decodes_before_filter"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_nfd_foreign_input_drops_after_nfc"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_control_and_fffd_stripped"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_quote_dash_normalization_without_resurrection"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_clean_text_never_raises"
        status: pass
    human_judgment: false
  - id: D2
    description: "Full audit fixture battery — 11 foreign drop-cases vanish whole, numerics excluded via both gates, hyphen compounds validated per-segment, empty-after-clean flows through"
    requirement: "TOK-02"
    verification:
      - kind: unit
        ref: "tests/test_cleaning.py#test_audit_drop_fixtures_vanish_whole"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_numeric_tokens_excluded_from_counts"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_hyphen_per_segment_validation"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_empty_after_clean_flows_through"
        status: pass
    human_judgment: false

# Metrics
duration: 2min
completed: 2026-10-16
status: complete
---

# Phase 1 Plan 02: Expansion Ordering + Fixture Battery Summary

**Full audit fixture battery with entity/NFD ordering pins — all 11 foreign drop-cases vanish whole, numerics excluded via both gates, empty-after-clean flows through**

## Performance

- **Duration:** 2 min
- **Started:** 2026-10-16T17:44:16Z
- **Completed:** 2026-10-16T17:46:04Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Ordering guarantees pinned: `&eacute;` decodes to `é` then drops (never a literal entity or countable token), NFD `e` + combining acute drops after NFC, control chars/`�` vanish with newlines preserved, `„ " " « » — –` normalize with no `COVID-19`→`COVID` resurrection
- Complete audit §2 battery: `Schrödinger`, `Besançon`, `Turčianske`, `Corrèze`, `Hübner`, `Maréchal`, `désintéressement`, `Führer`, `naïve`, `Linköping`, `Saint-Étienne-la-Geneste` all drop whole (no `H`/`bner`/`tienne-la` salvage); `2012`/`model3`/`COVID-19` excluded via both `clean_text()` and `is_valid_token()`; `Ala`/`chrząszcz`/`źdźbło`/`biało-czerwony` retained
- Empty-after-clean proven at both levels: zero-count paras take the `chunk_text_stream` skip path, fully-dropped docs flow through the writer gate as empty strings with zero TF/DF and no error
- Full gates green: `pytest tests/ -q` 41 passed 1 skipped; `ruff check src/ tests/` clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Ordering guarantees — unescape-before-filter, NFC-first, control stripping** - `6127628` (test)
2. **Task 2: Full fixture battery — numeric policy, hyphen segments, empty-after-clean** - `6d61f95` (test)

**Plan metadata:** (see commit below)

## Files Created/Modified
- `src/polish_corpus/text_cleaning.py` - One-word step-3 comment fix (`&eacute;` becomes `é`, not `e`); ordering logic itself verified correct, unchanged
- `tests/test_cleaning.py` - 13 ordering tests + 22 fixture-battery test cases (was 5 items, now 40)

## Decisions Made
- NFD fixtures written as explicit `\u0301` escapes rather than literal combining characters — verified via byte inspection that literals were genuinely decomposed, then converted so a future editor save can never silently NFC-normalize the fixture and void the ordering test.
- `tienne-la` validity asserted only through `clean_text()` whole-token drop, not `is_valid_token()` — per-segment validation correctly accepts Polish-only segments, so the no-salvage guarantee is pinned at the clean stage where it actually lives.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Chunk-threshold assumption in empty-after-clean test**
- **Found during:** Task 2 (Full fixture battery)
- **Issue:** Test called `chunk_text_stream` with defaults (`target_words=500`), so the 5-word surviving paragraph fell below `min_words` and no doc was yielded — assertion failed, not a pipeline bug
- **Fix:** Passed explicit `target_words=5, min_words=1` so the test exercises the skip-empty path rather than the sizing gate
- **Files modified:** tests/test_cleaning.py
- **Verification:** `pytest tests/ -q` green
- **Committed in:** 6d61f95 (Task 2 commit)

**2. [Rule 1 - Bug] SIM300 Yoda condition in entity test**
- **Found during:** Task 2 (ruff gate)
- **Issue:** `"e" == t` flagged by ruff SIM300
- **Fix:** Rewrote as `t == "e"`
- **Files modified:** tests/test_cleaning.py
- **Verification:** `ruff check src/ tests/` clean
- **Committed in:** 6d61f95 (Task 2 commit)

**3. [Rule 2 - Missing Critical] Step-3 comment misstated the decoded character**
- **Found during:** Task 1 (Ordering guarantees)
- **Issue:** Comment read "`&eacute;` becomes e" — wrong; it becomes `é`, and the distinction is the entire point of unescape-before-filter
- **Fix:** Corrected to "`&eacute;` becomes é and is then dropped, not passed through"
- **Files modified:** src/polish_corpus/text_cleaning.py
- **Verification:** Code review; behavior test `test_entity_decodes_before_filter` passes
- **Committed in:** 6127628 (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical comment)
**Impact on plan:** All auto-fixes necessary for correctness of tests/comments. No scope creep — no production ordering logic changed.

## Issues Encountered
None — implementation ordering from 01-01 was already correct; this plan pinned it with tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 1 success criteria 2–4 now fully pinned by tests (foreign drops, entity ordering, numeric exclusion, hyphen retention); criterion 1 (stored/counts agreement) carried over from 01-01
- Ready for Phase 2 source hardening — `clean_text()` is the stable choke point to build on
- No blockers

## Self-Check: PASSED

- `src/polish_corpus/text_cleaning.py` and `tests/test_cleaning.py` exist with new content
- Commits `6127628` and `6d61f95` are ancestors of HEAD
- `pytest tests/ -q`: 41 passed, 1 skipped; `ruff check src/ tests/`: all checks passed

---
*Phase: 01-cleaning-stage-shared-tokenizer*
*Completed: 2026-10-16*
