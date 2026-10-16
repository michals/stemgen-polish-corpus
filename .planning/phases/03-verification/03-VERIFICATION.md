---
phase: 03-verification
verified: 2026-10-16T20:00:00Z
status: passed
score: 6/6 must-haves verified
---

# Phase 03: Verification — Verification Report

**Phase Goal:** Corpus-scale proof that docs contain only valid Polish word
tokens — audit rates in build_summary.json as the acceptance signal, all 14
quality-audit section-2 rows pinned, full compact-tier rebuild scanning zero
foreign fragments via an independent gate.

**Verified:** 2026-10-16 (independent re-verification, goal-backward)
**Status:** VERIFIED — phase goal holds
**Re-verification:** No — initial verification (review follow-up commit included)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | build_summary.json reports foreign_fragment_rate, digit_token_rate, and per-genre rates as the acceptance signal | ✓ VERIFIED | `dist/compact/build_summary.json` → `audit_rates.global` + `audit_rates.per_genre` (4 genres); global foreign 0.0, digit 0.0005987…; per-genre foreign 0.0 everywhere. Key flows verbatim from `BalancedCorpusWriter.summary()` → `builder.py:276`. |
| 2 | Writer-reported rates are input-honest (drops counted at the add_document choke point; sizing-path drops never double-counted) | ✓ VERIFIED | `corpus_sampler.py:94-103` — accumulation only in `add_document()`; `chunk_text_stream` cleans via `clean_text` with no counter path. Pinned by `test_sizing_path_does_not_double_count` + `test_empty_after_clean_records_drops_without_quota` (pass). |
| 3 | A quick-test/full build emits the audit_rates key end-to-end | ✓ VERIFIED | Full compact-tier `dist/compact/build_summary.json` on disk contains top-level `audit_rates` mirroring `summary["audit_rates"]` (builder.py:274-276). |
| 4 | Every audit §2 fixture row maps to an explicit passing assert (no orphan fragments for any of the 14 inputs) | ✓ VERIFIED | All 14 rows grep-pinned in `tests/test_verification.py` (`Béziera`, `Besançon`, `Turčianske`, `Saint-Étienne-la-Geneste`, `Corrèze`, `Schrödinger`, `Hübner`, `Maréchal`, `désintéressement`, `Führer`, `café`, `naïve`, `COVID-19`, `Linköping`) + 3 source variants via `test_audit_row_leaves_no_salvage` (17 cases, pass). |
| 5 | A full-tier (compact) rebuild shows zero foreign fragments in docs and counts, verified by an independent scan script | ✓ VERIFIED | `scripts/verify_zero_fragments.py --dist-dir dist/compact` → exit 0, `gate: PASS`; 0 fragments in all 5 genre groups (4,458 docs, 2.28M tokens), 0 invalid GT words (262,658 words). Gate re-tokenizes stored bytes with shared `tokenize`/`is_valid_token`, never reads writer memory. |
| 6 | Writer-reported audit rates cross-check against the independent scan (no self-grading) | ✓ VERIFIED | Gate output: `stored_counts_agree OK`, `tokens_kept_agree OK`, `rate_arithmetic_ok OK`, `zero_fragments OK`; writer global foreign 0.0 vs script token_rate 0.000000 agree. |

**Score:** 6/6 truths verified

### Evidence Chain (rates slice → fixture pins → independent gate PASS)

1. **Rates slice:** `dist/compact/build_summary.json` → `audit_rates.global = {foreign_fragment_rate: 0.0, digit_token_rate: 0.000599, dropped_total: 1314, foreign_dropped: 0, digit_dropped: 1314, tokens_kept: 2193107}`; per-genre foreign rate 0.0 in all 4 genres (digit drops only in spoken_forum seed numbering, 2 per seed doc × 657).
2. **Fixture pins:** 14/14 quality-audit §2 rows pinned by audit-row case ID in `test_audit_row_leaves_no_salvage` (+ `Turčianske Teplice`, `Mein Führer`, `Anthé` variants); historic fragments (`ziera`, `Besan`, `caf`, `COVID`, …) proven absent from `tokenize(clean_text(dirty))` output at the correct level.
3. **Independent gate PASS on full rebuild:** `gate: PASS`, exit 0 — per-genre 0 fragments, GT 0 invalid / tf_total 2,279,296, all four cross-checks OK. Substantive proof is on stored bytes, not counters (writer-side `foreign_dropped` is 0 on real-source genres by the choke-point-only design; the gate verifies the artifacts themselves).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/polish_corpus/text_cleaning.py` | `AuditCounts` + `audit_clean()`, `clean_text` as delegation | ✓ VERIFIED | `AuditCounts` (L47), `audit_clean` (L104), `clean_text` → `audit_clean(t)[0]` (L175); delegation pinned by test battery |
| `src/polish_corpus/corpus_sampler.py` | Choke-point counters + `audit_rates` in `summary()` | ✓ VERIFIED | Counters only in `add_document` (L94-103); `audit_rates` global + per-genre (L181-183); `Any` typing fix present (L169) |
| `src/polish_corpus/builder.py` | `audit_rates` key in `build_summary.json` | ✓ VERIFIED | Top-level key verbatim from writer summary (L276) + intentional-duplication comment (L274-275) |
| `tests/test_verification.py` | Rate arithmetic + 14-row pins + gate tests | ✓ VERIFIED | 31 tests pass; exact arithmetic, no-double-count, empty-after-clean, delegation, 17 no-salvage cases, synthetic dirty/clean gate tests |
| `scripts/verify_zero_fragments.py` | Independent gate, exit 0/1 discipline | ✓ VERIFIED | `scan_text`/`scan_corpus_zip`/`scan_ground_truth`/`check_dist_dir` import-clean; X1–X4 cross-checks; `[Verify]` tags |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `audit_clean` | `clean_text` | single implementation, delegation | WIRED | No parallel implementation to drift; equivalence test passes |
| writer counters | `build_summary.json` | `summary()["audit_rates"]` verbatim | WIRED | Gate reads the key directly and recomputes arithmetic (X3) |
| gate script | stored artifacts | re-tokenize zip + parquet bytes | WIRED | Never reads writer memory; mismatch fails (no self-grading) |
| no-salvage asserts | `tokenize(clean_text(dirty))` | emptiness per audit row | WIRED | Pins non-generation at tokenizer-output level, not `is_valid_token` on fragments |

### Independent Re-verification Runs (this session)

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Full suite | `.venv/bin/python -m pytest tests/ -q` | 113 passed in 0.18s | ✓ PASS |
| Verification tests | `.venv/bin/python -m pytest tests/test_verification.py -q` | 31 passed | ✓ PASS |
| Lint | `ruff check src/ tests/ scripts/` | All checks passed | ✓ PASS |
| Independent gate | `.venv/bin/python scripts/verify_zero_fragments.py --dist-dir dist/compact` | exit 0, gate: PASS, 0 fragments all genres, 0 invalid GT, X1–X4 OK | ✓ PASS |
| Fixture pins | grep 14 audit rows in test_verification.py | 14/14 present | ✓ PASS |
| build_summary.json | read `audit_rates` global + per-genre | foreign 0.0 everywhere | ✓ PASS |

### Review Follow-up (03-REVIEW.md → commit d96d35b)

Review found 0 critical, 3 warnings + 4 info. Commit `d96d35b`
("fix(03-review): gate FAIL-on-corrupt, Any typing, token-rate reporting,
review notes") is an ancestor of HEAD. Fixes confirmed present in code:

| Finding | Fix | Confirmed |
|---------|-----|-----------|
| WR-01 gate crashes on corrupt artifacts | try/except around `scan_corpus_zip` (`BadZipFile`) + `scan_ground_truth` (generic) appending to `report.errors` | ✓ present, `verify_zero_fragments.py:186-193` |
| WR-02 `dict[str, any]` annotation | `from typing import Any`, `dict[str, Any]` | ✓ present, `corpus_sampler.py:15,169` |
| WR-03 fragment "rate" mixes violation kinds | token-channel-only `token_rate` (`invalid-token` prefix filter) | ✓ present, `verify_zero_fragments.py:233-240` |
| IN-01 literal U+FFFD | `"\ufffd"` escape | ✓ present, L56 |
| IN-03 common-mode blindness overclaim | docstring scoping note (X4 vs no-salvage tests) | ✓ present, L12-14 |
| IN-04 `audit_rates` written twice | intentional-duplication comment | ✓ present, `builder.py:274-275` |
| IN-02 gate in-memory GT columns | Documented limitation, fine at current scale; no action required | N/A (info) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VER-01 | 03-02 | Pin audit §2 fixture table against `clean_text()` + shared validator | ✓ SATISFIED | 14/14 rows + 3 variants, `test_audit_row_leaves_no_salvage` passes |
| VER-02 | 03-02 | Full-tier rebuild verifies zero foreign fragments in docs and counts | ✓ SATISFIED | Full compact rebuild + gate exit 0, X1–X4 OK |
| VER-03 | 03-01 | `build_summary.json` reports corpus audit rates as acceptance signal | ✓ SATISFIED | `audit_rates` global + per-genre, foreign/digit rates present |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| — | None — no TODO/FIXME/XXX/placeholder in phase files; no stub returns; no hardcoded empty data flowing to output | — | None |

### Human Verification Required

None — all truths verified programmatically; no visual, real-time, or external-service behavior in scope.

### Gaps Summary

No gaps. Phase goal holds end-to-end: rates slice → fixture pins → independent gate PASS on the full compact-tier rebuild.

---
_Verified: 2026-10-16_
_Verifier: the agent (gsd-verifier)_
