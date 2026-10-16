---
phase: 03-verification
reviewed: 2026-10-16T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/polish_corpus/text_cleaning.py
  - src/polish_corpus/corpus_sampler.py
  - src/polish_corpus/builder.py
  - tests/test_verification.py
  - scripts/verify_zero_fragments.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-10-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 3 (Verification) scope: `AuditCounts` + `audit_clean`/`clean_text`
in `text_cleaning.py`, per-genre audit counters and `audit_rates` in
`corpus_sampler.py`, the `audit_rates` key in `builder.py`'s
`build_summary.json`, plus `tests/test_verification.py` and
`scripts/verify_zero_fragments.py`. All 31 tests in `test_verification.py`
pass under the project venv (`.venv/bin/python -m pytest`), and `ruff check`
is clean on all five files.

Against the five focus areas: (1) delegation equivalence holds —
`clean_text` is a one-line projection of `audit_clean` with no parallel
implementation to drift, pinned by a parametrized test; (2) counter honesty
holds — drops accumulate only in `BalancedCorpusWriter.add_document`, and
`chunk_text_stream` cleans via `clean_text` (no counter path), so sizing-path
drops cannot double-count; (3) division-by-zero is guarded on both sides
(`if denom else 0.0` in `_audit_rate_entry`, same shape in
`_rates_recompute_ok`); (4) the gate re-derives every checked number from
stored bytes and any cross-check mismatch fails — with one robustness hole
(WR-01: corrupt artifacts crash the gate instead of producing a FAIL report);
(5) no new full-corpus in-memory structures in the build path — with one
caveat (IN-02: the gate itself materializes full GT columns).

No BLOCKERs. Three warnings and four info items below.

## Warnings

### WR-01: Gate crashes instead of FAIL on corrupt/unreadable artifacts

**File:** `scripts/verify_zero_fragments.py:169-214`
**Issue:** `check_dist_dir` wraps only the `build_summary.json` read in
try/except. `scan_corpus_zip` (`zipfile.BadZipFile` on a truncated
`corpus.zip`) and `scan_ground_truth` (`pyarrow` errors on a corrupt
parquet, `ValueError` from `zip(words, tfs, strict=True)` on ragged
columns) propagate uncaught. The process exits nonzero via traceback, so
CI still fails closed — but there is no `[Verify] gate: FAIL` report, no
`report.errors` entry, and `main()`'s exit-code contract (0 iff pass) is
satisfied only by accident of the interpreter. A gate whose failure mode
is "traceback, no report" is harder to triage and violates its own
docstring ("Exit 0 iff all cross-checks pass; nonzero otherwise" —
 callers expect an int, not an exception).
**Fix:**
```python
try:
    report.genres, stored_tf = scan_corpus_zip(zip_path)
except zipfile.BadZipFile as err:
    report.errors.append(f"unreadable corpus.zip: {err}")
    return report
try:
    report.gt, gt_tf = scan_ground_truth(parquet_path)
except Exception as err:  # ArrowInvalid, ValueError (strict zip), OSError
    report.errors.append(f"unreadable ground_truth.parquet: {err}")
    return report
```

### WR-02: `summary()` return annotation misuses builtin `any` as a type

**File:** `src/polish_corpus/corpus_sampler.py:168`
**Issue:** `def summary(self) -> dict[str, any]:` uses the builtin function
`any`, not `typing.Any`. It only survives because
`from __future__ import annotations` keeps the annotation lazy; any
runtime introspection (`typing.get_type_hints`) or strict type checker
resolves it to the `any` function object, not a type. Copy-paste of this
signature into a module without the future import would raise `TypeError`
at def time.
**Fix:**
```python
from typing import Any
def summary(self) -> dict[str, Any]:
```

### WR-03: `print_report` fragment "rate" mixes violation kinds over tokens

**File:** `scripts/verify_zero_fragments.py:221`
**Issue:** `rate = len(scan.violations) / scan.tokens` divides a
char-plus-token violation count (`scan_text` appends one entry per invalid
`TOKEN_RE` hit *and* one per offending character, so a single `café`
yields both `invalid-token` fragments and a `foreign-char` entry) by a
token count. The quotient can exceed 1.0 and is not comparable to the
writer's `foreign_fragment_rate` printed a few lines below, inviting a
misreading that the gate "measures a higher rate than the writer
reported" when both agree the build is dirty. Diagnostic-only, but this
is the number a human compares first.
**Fix:** report the two channels separately, e.g.
```python
tok_viol = sum(1 for v in scan.violations if v.split(": ", 1)[-1].startswith("invalid-token"))
rate = (tok_viol / scan.tokens) if scan.tokens else 0.0
```
or rename to `findings_per_token` with a comment that it is not a rate.

## Info

### IN-01: Replacement-character literal should be an escape

**File:** `scripts/verify_zero_fragments.py:51`
**Issue:** `if ch == "�"` embeds a literal U+FFFD. It works in a UTF-8
source tree, but a latin-1 round-trip or editor re-save silently changes
the comparison target, and reviewers cannot distinguish U+FFFD from
lookalikes (e.g. U+FFFD vs U+25A0) visually.
**Fix:** `if ch == "\ufffd" or ...`.

### IN-02: Gate materializes full GT columns and TF maps in memory

**File:** `scripts/verify_zero_fragments.py:107-147`
**Issue:** `scan_ground_truth` calls `to_pylist()` on both full columns
and builds two full-size dicts (`gt_tf`, plus `stored_tf` from the zip
scan). The build path itself streams (zip write + Counters), so this
introduces the only full-artifact-in-memory step in the phase scope.
Fine for compact/recommended tiers; unbounded for an extended-tier GT
with millions of rows. Flagged per the review's streaming-discipline
focus, not as a defect at current scale.
**Fix (when needed):** stream via `pq.ParquetFile.iter_batches` and
compare batched aggregates, or compare sorted chunk hashes instead of
full dicts.

### IN-03: Residual common-mode blindness in gate design (documented limitation)

**File:** `scripts/verify_zero_fragments.py:34-58`
**Issue:** The gate imports the public `TOKEN_RE` / `is_valid_token` /
`tokenize` contract it audits. A bug in that shared contract blinds both
writer and gate identically (e.g. if `TOKEN_RE` ever admitted `é`, dirty
docs would pass X4). Relatedly, the gate's token-level check cannot
detect *salvaged* Polish-looking fragments: had a buggy cleaner kept
`ziera` from `Béziera`, the stored text would contain only valid Polish
letters and the gate would PASS — detection of salvage lives in the unit
tests (`test_audit_row_leaves_no_salvage`), not the gate. The char-level
scan covers residue that retains foreign characters, which is the
actually-observable stored-bytes property, so this is a correctly scoped
limitation — but the module docstring's "artifacts themselves are clean"
overclaims slightly: it means "no observable foreign/digit/control
residue," not "no salvage derivation occurred."
**Fix:** one docstring sentence, e.g. "X4 detects observable residue in
stored bytes; absence of salvage derivation is pinned by
test_audit_row_leaves_no_salvage, not by this gate."

### IN-04: `audit_rates` written twice into `build_summary.json`

**File:** `src/polish_corpus/builder.py:267-280`
**Issue:** `audit_rates` appears both top-level and nested inside
`summary` (which already contains it via `writer.summary()`). The gate
tolerates both (`summary.get("audit_rates") or
summary.get("summary", {}).get("audit_rates")`), so this is harmless
redundancy, but two sources of the same truth can diverge if a future
edit mutates one copy.
**Fix:** write one copy (prefer top-level) and have the gate read one
location, or keep as-is with a comment noting the duplication is
intentional for backward compatibility.

---

_Reviewed: 2026-10-16T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
