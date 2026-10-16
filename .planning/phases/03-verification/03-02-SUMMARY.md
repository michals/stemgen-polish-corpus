---
phase: 03-verification
plan: 02
subsystem: testing
tags: [audit-trace, zero-fragment-gate, compact-rebuild, pytest, ruff, pyarrow]

# Dependency graph
requires:
  - phase: 03-verification plan 01
    provides: audit_clean/AuditCounts/audit_rates APIs the gate cross-checks
  - phase: 01-cleaning
    provides: clean_text/tokenize/is_valid_token contract the gate re-applies
provides:
  - audit-trace pins for all 14 quality-audit.md section-2 rows plus 3 source variants
  - scripts/verify_zero_fragments.py independent corpus-scale gate (X1-X4, exit 0/1)
  - full compact-tier rebuild evidence scanning zero fragments (4,458 docs, 2.28M tokens)
affects: [verify-work acceptance, stemgen training-data confidence]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 4839
  tasks: 3
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns: [audit-row case IDs, independent stored-byte gate, writer-rate cross-check]

key-files:
  created: [scripts/verify_zero_fragments.py]
  modified: [tests/test_verification.py]

key-decisions:
  - "Gate cross-checks tokens_kept and rate arithmetic, never equality of input-side drop rates vs output-side fragment rates (different quantities by construction)"
  - "Single-char historic fragments pinned by exact-token absence only; substring checks reserved for len>=3 to avoid noise"
  - "Task 3 has no commit: dist/compact is gitignored, so build evidence lives on disk and is recorded here"

patterns-established:
  - "Gate script keeps checker logic import-clean (argparse only under __main__) so tests import it via importlib"
  - "Synthetic dist-dir fixtures (raw zip + pyarrow parquet + summary JSON) prove the gate fails dirty and passes clean"

requirements-completed: [VER-01, VER-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "All 14 audit section-2 rows plus 3 source variants pinned by audit-ID parametrized asserts"
    requirement: "VER-01"
    verification:
      - kind: unit
        ref: "tests/test_verification.py#test_audit_row_leaves_no_salvage (17 cases)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Independent gate script flags synthetic dirty corpus and passes clean one"
    requirement: "VER-02"
    verification:
      - kind: unit
        ref: "tests/test_verification.py#test_gate_flags_synthetic_dirty_corpus"
        status: pass
      - kind: unit
        ref: "tests/test_verification.py#test_gate_passes_synthetic_clean_corpus"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full compact-tier rebuild scans zero fragments via the independent gate (exit 0)"
    requirement: "VER-02"
    verification:
      - kind: integration
        ref: "python scripts/verify_zero_fragments.py --dist-dir dist/compact (exit 0, X1-X4 OK)"
        status: pass
    human_judgment: false

# Metrics
duration: 30min
completed: 2026-10-16
status: complete
---

# Phase 03 Plan 02: Corpus-Scale Zero-Fragment Gate Summary

**All 14 audit rows pinned by ID with no-salvage asserts, plus an independent gate script proving a full 4,458-doc compact rebuild carries zero foreign fragments (exit 0, four cross-checks OK)**

## Performance

- **Duration:** 30 min
- **Started:** 2026-10-16T18:05:00Z (approx)
- **Completed:** 2026-10-16T18:36:39Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- `test_audit_row_leaves_no_salvage`: 17 parametrized cases (14 audit rows + `Turčianske Teplice`, `Mein Führer`, `Anthé` variants), each asserting exact post-clean leftovers plus named historic-fragment absence at the correct level (never `is_valid_token` on Polish-class fragments)
- `scripts/verify_zero_fragments.py`: stdlib + pyarrow gate re-tokenizing every stored doc and GT word, with X1 stored/counts agreement, X2 tokens_kept agreement, X3 rate-arithmetic recompute, X4 zero fragments; `[Verify]` tags, `sys.exit(0/1)`
- Full compact build (`Tier: compact`, NOT quick-test, 38.99s — all sources cache-hit): 4,458 docs, 2,279,296 tokens, 262,658 vocab; gate PASS with 0 fragments in every genre and 0 invalid GT words

## Task Commits

Each task was committed atomically:

1. **Task 1: VER-01 fixture consolidation — audit-trace plus no-salvage pins** - `0908e1f` (test)
2. **Task 2: Independent zero-fragment gate script** - `1cd6eaa` (feat)
3. **Task 3: Full-tier compact rebuild showing zero foreign fragments** - no commit (build artifacts under `dist/` are gitignored; nothing committable — evidence recorded below)

## Build Evidence (Task 3)

Per-genre gate output (`dist/compact`, exit 0):

| Genre | Docs | Tokens | Fragments | Origin |
|---|---|---|---|---|
| 01_nkjp_spoken_forum | 1,100 | 422,520 | 0 | 443 real + 657 seed fallback (source exhausted) |
| 02_nkjp_literature | 880 | 465,280 | 0 | all real (Wolne Lektury cache) |
| 03_nkjp_news | 660 | 411,825 | 0 | all real (news CSVs cache) |
| 04_wikipedia | 1,760 | 893,482 | 0 | all real (`wiki_pl.jsonl` 28MB present — no seed fallback, contrary to research expectation) |
| 99_morfeusz_paradigms | 58 | 86,189 | 0 | dictionary-derived (audit-excluded) |

Ground truth: 262,658 words, 0 invalid, tf_total 2,279,296 (equals writer total_tokens).
Writer audit rates: global foreign 0.0, digit 0.000599 (1,314 digit drops — all from spoken-forum seed numbering `Dokument numer N ...`, 2 per seed doc × 657); foreign_dropped 0 everywhere (see observation below).
Cross-checks: stored_counts_agree OK, tokens_kept_agree OK (2,193,107 == 422,520+465,280+411,825+893,482), rate_arithmetic_ok OK, zero_fragments OK.

Observation (not a deviation — no code changed): writer-side `foreign_dropped` is 0 on real-source genres because those docs arrive pre-cleaned via the `chunk_text_stream` sizing path, whose drops are uncounted by the 03-01 choke-point-only design. The stored-byte gate is therefore the substantive proof: it verifies the artifacts themselves, not the counters.

## Files Created/Modified

- `scripts/verify_zero_fragments.py` - Independent gate: scan_text/scan_corpus_zip/scan_ground_truth/check_dist_dir + argparse main
- `tests/test_verification.py` - 17 audit-trace cases + synthetic dirty/clean gate tests (31 tests in file, 113 suite-wide)

## Decisions Made

- Cross-check "agreement" defined as X1+X2+X3 numeric recomputation from stored bytes, not equality between input-side drop rates and output-side fragment rates — those are different quantities (writer foreign rate 0.0 vs script fragment rate 0.0 coincide here, but equality must never be asserted in general)
- Single-char historic fragments (`H`, `B`, `F`, `d`, `on`, `ze`, `na`, `ve`) pinned by exact-token absence only; substring checks apply at len>=3
- Gate mirrors (not imports) the private Polish-letter class so it shares only the public `TOKEN_RE`/`is_valid_token`/`tokenize` contract with the library

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Register gate module in sys.modules for dataclass import**
- **Found during:** Task 2 (gate unit tests)
- **Issue:** `importlib` file-location import without `sys.modules` registration broke `@dataclass` processing (`AttributeError: 'NoneType' has no __dict__`)
- **Fix:** `sys.modules["verify_zero_fragments"] = module` before `exec_module` in the test loader
- **Files modified:** tests/test_verification.py
- **Verification:** Both gate tests pass
- **Committed in:** 1cd6eaa (part of task commit)

**2. [Rule 1 - Bug] Explicit zip strict parameter for ruff B905**
- **Found during:** Task 2 (`ruff check src/ tests/ scripts/`)
- **Issue:** B905 `zip()` without explicit `strict=` in GT column iteration
- **Fix:** `zip(words, tfs, strict=True)` (same-table columns, always equal length)
- **Files modified:** scripts/verify_zero_fragments.py
- **Verification:** `ruff check` clean
- **Committed in:** 1cd6eaa (part of task commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both required for tests/lint to pass. No scope creep; gate never weakened.

## Issues Encountered

- Full build finished in ~39s instead of "tens of minutes" — all 12 source files plus PoliMorf were cache hits, so no downloads were needed; `wiki_pl.jsonl` (28MB) is present, so the expected wikipedia seed fallback did not occur (only spoken_forum needed 657 seed docs)
- `ruff format` is not a repo gate (11 pre-existing files unformatted); applied it to the two touched files only

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 success criteria 1–3 hold: `pytest tests/ -q` (113 passed), `ruff check src/ tests/ scripts/` clean, gate exit 0 on the full compact build
- Core Value proven at corpus scale: stored docs and GT contain zero foreign fragments through an independent checker that never trusts writer counters

## Self-Check: PASSED

- `scripts/verify_zero_fragments.py`, `tests/test_verification.py` exist with new content
- Commits `0908e1f`, `1cd6eaa` both ancestors of HEAD
- `dist/compact/{corpus.zip,ground_truth.parquet,build_summary.json}` present on disk (gitignored by design)

---
*Phase: 03-verification*
*Completed: 2026-10-16*
