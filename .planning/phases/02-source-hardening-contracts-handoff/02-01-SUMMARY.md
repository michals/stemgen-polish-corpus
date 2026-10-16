---
phase: 02-source-hardening-contracts-handoff
plan: 01
subsystem: corpus-pipeline
tags: [source-hardening, dedup, url-strip, email-strip, text-cleaning, regression-tests]

# Dependency graph
requires:
  - phase: 01-cleaning-stage-shared-tokenizer
    provides: text_cleaning.py choke point with clean_text/tokenize/is_valid_token
provides:
  - blake2b seen-guard in all four iter_*_docs yield loops (no DF skew from re-passes)
  - URL/email strip as a load-bearing clean_text() step before the token DROP
  - tests/test_source_hardening.py pinning both guards plus Phase 1 spot-checks
affects: [WL boilerplate filter (plan 02-02), tokenizer contract, full-tier rebuild gate]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 12000
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns: [content-hash seen-guard, choke-point strip step]

key-files:
  created: [tests/test_source_hardening.py]
  modified: [src/polish_corpus/text_sources.py, src/polish_corpus/text_cleaning.py]

key-decisions:
  - "Dedup hashes the chunked doc (post-chunk_text_stream), not raw paragraphs — doc-level identity is the invariant"
  - "URL/email strip lives in clean_text(), not per-genre helpers — docs/counts agreement by construction across all four genres"
  - "Dedup tests stub chunk_text_stream via manual attribute swap, not monkeypatch fixture — keeps the plain-function test pattern with zero fixtures"

patterns-established:
  - "Guard tests assert post-conditions (exact-once yields, fragments absent) rather than guard internals, so loop shapes stay free to evolve"

requirements-completed: [SRC-01, SRC-03]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "Dedup seen-guard — a 2-doc source asked for 5 docs yields exactly 2 distinct docs in all four iterators, with no DF skew from re-passes"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "tests/test_source_hardening.py#test_short_source_yields_each_doc_exactly_once"
        status: pass
    human_judgment: false
  - id: D2
    description: "URL/email strip — https/http/www and jan@domena.pl vanish whole with Polish retained; URL-only input cleans to empty and takes the skip-empty path"
    requirement: "SRC-03"
    verification:
      - kind: unit
        ref: "tests/test_source_hardening.py#test_url_stripped_whole_with_polish_retained"
        status: pass
      - kind: unit
        ref: "tests/test_source_hardening.py#test_url_only_paragraph_cleans_empty_and_skips_chunker"
        status: pass
      - kind: unit
        ref: "tests/test_source_hardening.py#test_email_stripped_whole_with_surroundings_retained"
        status: pass
      - kind: unit
        ref: "tests/test_source_hardening.py#test_phase1_spot_checks_hold_after_url_strip"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-10-16
status: complete
---

# Phase 2 Plan 01: Tracer Source Guards Summary

**Cross-cutting source guards through the Phase 1 choke point — dedup seen-set plus URL/email strip, proven by a quick-test build plus targeted asserts**

## Performance

- **Duration:** 15 min
- **Started:** 2026-10-16T18:00:00Z
- **Completed:** 2026-10-16T18:15:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Dedup guard in all four `iter_*_docs` loops: function-local `seen` set of blake2b (`digest_size=16`) doc digests skips re-yielded chunks, so short sources terminate after one distinct pass instead of inflating DF
- URL/email strip as new `clean_text()` step 5 (after unescape/control-strip, before token DROP): `https://`, `http://`, `www.` and `user@host` forms vanish whole — no `http`/`com`/`user` fragments reach docs or TF/DF — while surrounding Polish survives
- Regression file `tests/test_source_hardening.py` with 11 cases: dedup exact-once across all four iterators, parametrized URL/email drop-retain, URL-only skip-empty path, Phase 1 spot-checks (`café` drops, `biało-czerwony` retained)
- Full gates green: `pytest tests/ -q` 58 passed 1 skipped (skip is the pre-existing pyarrow-gated smoke test under system python); `ruff check src/ tests/` clean; venv quick-test build exits 0 (21 docs, 5,731 tokens, GT + split + Snowball exports)

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end source guards — dedup seen-set plus URL/email strip** - `da68013`
2. **Task 2: Regression tests pinning the tracer guards** - `e1b19b7`

**Plan metadata:** (see commit below)

## Files Created/Modified

- `src/polish_corpus/text_sources.py` - stdlib `import hashlib` plus identical 6-line seen-guard hunk in all four `iter_*_docs` yield loops
- `src/polish_corpus/text_cleaning.py` - module-level `_URL_RE`/`_EMAIL_RE` constants and new pipeline step 5 applying both subs; later steps renumbered 6→7, 7→8
- `tests/test_source_hardening.py` - NEW: 11 plain-function tests in the `test_cleaning.py` pattern (no fixtures)

## Decisions Made

- Dedup digests the chunked doc, not raw paragraphs — identical paragraphs legitimately recur across docs; doc-level identity is the invariant (per RESEARCH §1).
- Strip placed at the `clean_text()` choke point rather than per-genre helpers — single position keeps stored-docs/counts agreement by construction and covers forum URLs for free.
- Dedup test stubs `chunk_text_stream` via manual module-attribute swap with try/finally restore instead of the `monkeypatch` fixture — keeps the file fixture-free per the plan's plain-function pattern.

## Deviations from Plan

None — both tasks executed verbatim from the plan (RESEARCH §1 loop shape, §2 regexes and positioning). The pipeline-comment renumbering (6→7, 7→8) is the mechanical consequence of inserting step 5, not a scope change.

---

**Total deviations:** 0
**Impact on plan:** N/A

## Issues Encountered

- Quick-test build under system `python3` fails at GT parquet export with `ModuleNotFoundError: pyarrow` — environmental, not caused by this plan (stdlib-only changes; archive finalization with both guards active succeeded). Re-ran under `.venv/bin/python` (pyarrow present): exit 0, all artifacts exported. The `test_quick_test_run` smoke test likewise skips without pyarrow by design (`importorskip`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Tracer slice complete: dedup + URL/email guards flow through the single `clean_text`/iterator path every later doc uses
- Plan 02-02 builds on top: WL boilerplate `_is_boilerplate()` helper plus tokenizer-contract and ground-truth-issues handoff docs
- No blockers

## Self-Check: PASSED

- `src/polish_corpus/text_sources.py`, `src/polish_corpus/text_cleaning.py`, and `tests/test_source_hardening.py` exist with new content
- Commits `da68013` and `e1b19b7` are ancestors of HEAD
- `pytest tests/ -q`: 58 passed, 1 skipped; `ruff check src/ tests/`: all checks passed

---
*Phase: 02-source-hardening-contracts-handoff*
*Completed: 2026-10-16*
