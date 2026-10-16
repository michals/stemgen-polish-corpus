# Phase 3: Verification - Pattern Map

**Mapped:** 2026-10-16
**Files analyzed:** 4 (2 modified, 1 new test extension, 1 new script)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/polish_corpus/text_cleaning.py` (MODIFY) | utility | transform | itself (numbered pipeline + `_drop_token` cause split) | exact |
| `src/polish_corpus/corpus_sampler.py` (MODIFY) | service | streaming | itself (`token_counts` per-genre dict pattern `:69`) | exact |
| `src/polish_corpus/builder.py` (MODIFY) | orchestrator | batch | itself (summary JSON block `:267-279`) | exact |
| `tests/test_verification.py` (NEW) | test | batch | `tests/test_source_hardening.py` (writer + tmp_path pattern) | role-match |
| `scripts/verify_zero_fragments.py` (NEW) | script | batch | none in repo — stdlib `zipfile` + `pyarrow.parquet` read pattern | partial |

## Pattern Assignments

### `text_cleaning.py` — `audit_clean()` beside `clean_text()`

**Analog:** itself. `AuditCounts` as `typing.NamedTuple` (typed fields, zero methods) following the plain-tuple GT-row convention used across the codebase. `clean_text(text)` becomes `return audit_clean(text)[0]` — behavior identical, single implementation. Cause split reuses the existing `_drop_token` digit-vs-foreign branch order (digit check first, `:49-51`); URL/email counts via `re.subn` (stdlib, no new pattern shape).

### `corpus_sampler.py` — per-genre audit counters

**Analog:** itself — `self.token_counts: dict[str, int] = {genre: 0 ...}` (`:69`). Add `self.audit_counts: dict[str, Counter]` keyed the same way (including the `if genre not in` lazy-init pattern from `add_document :82-84`). `summary()` gains `"audit_rates"` computed by a small pure helper (rate arithmetic testable without a writer instance).

### `builder.py` — summary JSON extension

**Analog:** itself (`:267-279`). Additive `"audit_rates": corpus_summary["audit_rates"]` key — no existing keys touched, no parquet/zip layout change (compatibility constraint holds).

### `tests/test_verification.py` + `scripts/verify_zero_fragments.py`

**Tests analog:** `test_source_hardening.py` — plain functions, `BalancedCorpusWriter` + `tmp_path` round-trip, parametrized tables with audit-§2 row references in case IDs. **Script analog (partial):** no in-repo CLI script precedent — follow `builder.py` print-tag convention (`[Verify]`) and exit-code discipline (`sys.exit(0/1)`); `argparse` with `--dist-dir` defaulting to `dist/compact` per `cli.py` flag style.

---

## Shared Patterns

Same as Phases 1–2: one-line PEP 257 docstrings, print-free library functions, lenient parsing (`errors="replace"` on zip/parquet text reads where applicable), ≤100 cols, `ruff` clean.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Corpus-scale zip+parquet scan loop | script | batch | No precedent — follow RESEARCH §3 contract (per-genre counts, nonzero exit on fragment, cross-check vs summary rates). |

## Metadata

**Analog search scope:** `src/polish_corpus/`, `tests/`, `scripts/` (absent — new dir)
**Files scanned:** 5 (`text_cleaning.py`, `corpus_sampler.py`, `builder.py`, `test_source_hardening.py`, `config.py`)
**Pattern extraction date:** 2026-10-16
