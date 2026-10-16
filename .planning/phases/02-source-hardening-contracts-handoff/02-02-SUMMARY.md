---
phase: 02-source-hardening-contracts-handoff
plan: 02
subsystem: corpus-pipeline
tags: [source-hardening, wolne-lektury, boilerplate, tokenizer-contract, gt-handoff, regression-tests]

# Dependency graph
requires:
  - phase: 02-01 tracer source guards
    provides: text_sources.py with hashlib seen-guards, clean_text() URL/email strip, tests/test_source_hardening.py
provides:
  - _is_boilerplate() WL filter replacing the three literal checks in iter_literature_docs
  - docs/tokenizer-contract.md reuse contract (TOK-03) and repo-root ground-truth-issues.md handoff (DOC-01)
  - Boilerplate drop/retention pins in tests/test_source_hardening.py
affects: [full-tier rebuild gate]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 14000
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns: [short-line-gated structural filter, docs-only handoff]

key-files:
  created: [docs/tokenizer-contract.md, ground-truth-issues.md]
  modified: [src/polish_corpus/text_sources.py, tests/test_source_hardening.py]

key-decisions:
  - "Structural boilerplate regexes gated to lines < 80 chars; substring checks ungated — mid-sentence rozdział prose is never dropped"
  - "Contract doc pins actual 8-step clean_text() ordering (URL/email strip is step 5), not the RESEARCH §4 shorthand of 7 steps"
  - "Drop-table entries use WL-realistic marker forms (CZĘŚĆ II, Księga II) — trailing-prose forms like CZĘŚĆ DRUGA correctly do NOT match the anchored chapter pattern"

patterns-established:
  - "Boilerplate tests assert classification post-conditions (drop vs retain tables) rather than regex internals, so the pattern set stays free to evolve"

requirements-completed: [SRC-02, TOK-03, DOC-01]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "WL boilerplate filter — headers, chapter markers, roman/digit-alone lines, separators, editor notes, end markers drop; mid-sentence rozdział prose and normal narrative retained"
    requirement: "SRC-02"
    verification:
      - kind: unit
        ref: "tests/test_source_hardening.py#test_boilerplate_lines_drop"
        status: pass
      - kind: unit
        ref: "tests/test_source_hardening.py#test_prose_with_boilerplate_words_retained"
        status: pass
      - kind: unit
        ref: "tests/test_source_hardening.py#test_is_boilerplate_never_raises"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tokenizer reuse contract — exact TOKEN_RE, is_valid_token rules, clean_text ordering, tokenize def, copy-paste snippet, v1 note"
    requirement: "TOK-03"
    verification:
      - kind: review
        ref: "docs/tokenizer-contract.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "GT issues handoff — OOV fallback, proper-noun leakage, oov_self_lemma_rate proposal, each with file:line evidence and not-implemented-here banner"
    requirement: "DOC-01"
    verification:
      - kind: review
        ref: "ground-truth-issues.md"
        status: pass
    human_judgment: false

# Metrics
duration: 10min
completed: 2026-10-16
status: complete
---

# Phase 2 Plan 02: Expansion Boilerplate + Contracts Summary

**WL boilerplate filtered with prose-retention pins plus the two docs-only handoffs — tokenizer contract and GT issues, full suite and lint green**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-16T18:08:00Z
- **Completed:** 2026-10-16T18:18:43Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `_is_boilerplate()` in `text_sources.py`: module-level `_BOILERPLATE_RES`
  (chapter markers, roman-numeral-alone, digit-alone, separator runs, editor-note
  prefixes, end markers per RESEARCH §3) plus closed substring list folding in and
  replacing the three existing literal checks — called per WL line before the
  `len(line) > 20` yield gate, never raises, structural patterns gated to short
  lines (< 80 chars)
- 26 new test cases in `tests/test_source_hardening.py`: 19-line boilerplate
  drop table, 4-case prose-retention table (mid-sentence `rozdział` survives),
  leniency asserts — `pytest tests/test_source_hardening.py -q` 34 passed
- `docs/tokenizer-contract.md` (TOK-03): exact `TOKEN_RE`, `is_valid_token()`
  rules, `clean_text()` step ordering with load-bearing positions, `tokenize()`
  def, copy-paste reuse snippet, contract-v1 version note — no code changes
- `ground-truth-issues.md` (DOC-01) at repo root: OOV `(word, word)` fallback
  (`builder.py:209`), proper-noun leakage into counts
  (`corpus_sampler.py:90-96` vs `morfeusz_extractor.py:89-92`), `oov_self_lemma_rate`
  proposal — each with file:line evidence and an explicit not-implemented-here banner
- Full gates green: `pytest tests/ -q` 82 passed; `ruff check src/ tests/` clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Wolne Lektury boilerplate filter plus tests** - `990c205`
2. **Task 2: Tokenizer contract doc and ground-truth handoff doc** - `d26b965`

**Plan metadata:** (see commit below)

## Files Created/Modified

- `src/polish_corpus/text_sources.py` - `_BOILERPLATE_RES` + `_BOILERPLATE_SUBSTRINGS`
  + `_is_boilerplate()`; `iter_literature_docs` line loop now calls the helper
  instead of the three literal checks
- `tests/test_source_hardening.py` - import of `_is_boilerplate` plus drop table,
  retention table, and never-raises tests (was 8 tests, now 34)
- `docs/tokenizer-contract.md` - NEW: stemgen-facing reuse contract (TOK-03)
- `ground-truth-issues.md` - NEW: repo-root upstream handoff (DOC-01)

## Decisions Made

- Structural regexes apply only to lines < 80 chars while substring checks
  (`Wolne Lektury`, `ISBN`, `Ten utwór`, …) are ungated — exact RESEARCH §3
  shape: over-drop guard lives inside the helper, not at the call site.
- Contract doc records the real 8-step `clean_text()` ordering (URL/email strip
  inserted as step 5 in plan 02-01) rather than the RESEARCH §4 "7-step"
  shorthand — the document pins what the code does.
- No GT export code changes and no stemgen changes per the plan's docs-only
  scope for TOK-03/DOC-01.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Drop-table entries that the anchored chapter regex correctly rejects**
- **Found during:** Task 1 (boilerplate tests, pre-run review)
- **Issue:** `CZĘŚĆ DRUGA` and `Księga pierwsza` carry trailing prose after the
  marker, so the full-line-anchored chapter pattern (`...$`) does not match
  them — asserting a drop would encode the over-drop the short-line gate and
  anchors are designed to prevent
- **Fix:** Replaced with WL-realistic bare-marker forms `CZĘŚĆ II` and
  `Księga II`, which the pattern matches
- **Files modified:** tests/test_source_hardening.py
- **Verification:** `pytest tests/test_source_hardening.py -q` 34 passed
- **Committed in:** 990c205 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (bug in test fixtures, not production logic)
**Impact on plan:** Fixture-only correction; no scope change — production regexes
taken verbatim from RESEARCH §3.

## Issues Encountered

None — RESEARCH §3 regexes behaved as specified on first run; both docs are
pure prose with no test gate beyond the shared full-suite run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 contract complete: SRC-01/SRC-03 (plan 01) + SRC-02/TOK-03/DOC-01
  (this plan) — all four raw-text noise paths hardened, both handoff docs in place
- Ready for the full-tier rebuild gate with audit stats showing zero foreign fragments
- No blockers

## Self-Check: PASSED

- `src/polish_corpus/text_sources.py`, `tests/test_source_hardening.py`,
  `docs/tokenizer-contract.md`, and `ground-truth-issues.md` exist with new content
- Commits `990c205` and `d26b965` are ancestors of HEAD
- `pytest tests/ -q`: 82 passed; `ruff check src/ tests/`: all checks passed

---
*Phase: 02-source-hardening-contracts-handoff*
*Completed: 2026-10-16*
