---
phase: 01-cleaning-stage-shared-tokenizer
plan: 01
subsystem: corpus-pipeline
tags: [text-cleaning, tokenizer, polish, corpus-sampler, regression-tests]

# Dependency graph
requires:
  - phase: quality-audit analysis
    provides: root-cause evidence (TOKEN_RE truncation, raw-text write) and fixture table
provides:
  - text_cleaning.py as sole owner of TOKEN_RE/is_valid_token/clean_text/tokenize
  - Writer-boundary gate in BalancedCorpusWriter.add_document (stored docs and TF/DF agree by construction)
  - Minimal regression tests pinning whole-token drops and count agreement
affects: [01-02 fixture battery, source hardening, audit rates, full-tier rebuild gate]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 2110
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns: [pure-function cleaning stage, single writer choke-point gate, shared tokenizer]

key-files:
  created: [src/polish_corpus/text_cleaning.py, tests/test_cleaning.py]
  modified: [src/polish_corpus/corpus_sampler.py]

key-decisions:
  - "Punctuation attached to Polish words does not trigger token drops — only digits and non-Polish letters do, so quote/dash normalization stays meaningful for retained words"
  - "Whitespace separators preserved through the token-drop filter and newlines survive collapse, so stored docs keep paragraph breaks"
  - "morfeusz_extractor.py left untouched — it carries VALID_WORD_RE, not TOKEN_RE, so no import swap applied"

patterns-established:
  - "text_cleaning.py follows the morfeusz_extractor.py pure-function pattern: PEP 257 one-line docstrings, typed signatures, stdlib-only imports, print-free"
  - "Numbered # 1-6 inline comments mark the load-bearing clean_text() ordering (NFC first, unescape before filter, filter before punctuation normalize)"
  - "test_cleaning.py follows the test_smoke.py plain-function pattern: no fixtures/classes, parametrized cases"

requirements-completed: [CLN-01, CLN-02, TOK-01]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "Shared cleaning/tokenizer module wired through the writer choke point; foreign/numeric tokens drop whole, biało-czerwony retained"
    requirement: "CLN-01"
    verification:
      - kind: integration
        ref: "pytest tests/test_smoke.py -q (quick-test build with gate active)"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_foreign_tokens_drop_whole"
        status: pass
      - kind: unit
        ref: "tests/test_cleaning.py#test_hyphenated_polish_compound_retained"
        status: pass
    human_judgment: false
  - id: D2
    description: "Stored doc text and TF/DF counts derive from the same cleaned text (re-tokenizing a stored doc reproduces its recorded counts)"
    requirement: "CLN-02"
    verification:
      - kind: integration
        ref: "tests/test_cleaning.py#test_stored_text_and_counts_agree"
        status: pass
    human_judgment: false
  - id: D3
    description: "Single shared tokenizer/validator used by the sampler for all counting"
    requirement: "TOK-01"
    verification:
      - kind: integration
        ref: "pytest tests/test_smoke.py -q (quick-test build with gate active)"
        status: pass
    human_judgment: false

# Metrics
duration: 4min
completed: 2026-10-16
status: complete
---

# Phase 1 Plan 01: Tracer Cleaning Gate Summary

**Shared Polish text-cleaning/tokenizer stage (`text_cleaning.py`) gating the corpus writer so stored docs and TF/DF agree, with whole-token foreign/numeric drops**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-16T17:40:43Z
- **Completed:** 2026-10-16T17:43:12Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- New `src/polish_corpus/text_cleaning.py` owns `TOKEN_RE` (moved verbatim), `is_valid_token()`, `clean_text()`, `tokenize()` with the locked NFC → strip → unescape → token-drop → normalize → collapse ordering
- `BalancedCorpusWriter.add_document` cleans as its first line before both `writestr` and counting; counting and `count_words` delegate to shared `tokenize()`; local `TOKEN_RE` copy deleted
- `Béziera`/`café`/`COVID-19` vanish whole through the writer (no `ziera`/`caf`/`COVID` fragments in zip text or TF/DF); `biało-czerwony` survives; quick-test build green with the gate active
- Minimal `tests/test_cleaning.py` pins the tracer slice: parametrized whole-token drops, hyphen retention, zip-vs-TF/DF agreement

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end cleaning gate** - `c4fa964` (feat)
2. **Task 2: Minimal regression tests** - `4de1f71` (test)

**Plan metadata:** (see commit below)

## Files Created/Modified
- `src/polish_corpus/text_cleaning.py` - Shared cleaning/tokenizer stage; sole TOKEN_RE owner
- `src/polish_corpus/corpus_sampler.py` - Writer gate (`clean_text` first line of `add_document`), counting via shared `tokenize()`, `count_words` delegates
- `tests/test_cleaning.py` - Tracer-minimum regression tests (drop/retain/agreement)

## Decisions Made
- Punctuation attached to Polish words does not trigger token drops — only digits and non-Polish Unicode letters do. Rationale: otherwise `„cytat"`-style quoted words would vanish and quote normalization would be pointless; URL stripping stays in Phase 2 scope.
- Whitespace separators preserved through the token-drop filter (`re.split` with capture) and newlines survive the final collapse, so stored docs keep paragraph breaks.
- `morfeusz_extractor.py` left untouched — it carries `VALID_WORD_RE`, not `TOKEN_RE`, so the plan's conditional import swap did not apply.
- Executed on new branch `agent-01-01-cleaning-stage` — HEAD was on protected `master`, so per the commit protocol work was re-homed to a per-plan branch before any commit.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tracer slice proven end-to-end; ready for plan 01-02 (full audit fixture battery: Schrödinger, Saint-Étienne-la-Geneste, NFD ordering, `&eacute;` ordering, numeric battery, empty-after-clean)
- No blockers

## Self-Check: PASSED

- `src/polish_corpus/text_cleaning.py` exists; `tests/test_cleaning.py` exists; `corpus_sampler.py` imports from `.text_cleaning` with no local `TOKEN_RE`
- Commits `c4fa964` and `4de1f71` are ancestors of HEAD
- `pytest tests/ -q`: 9 passed; `ruff check src/ tests/`: all checks passed

---
*Phase: 01-cleaning-stage-shared-tokenizer*
*Completed: 2026-10-16*
