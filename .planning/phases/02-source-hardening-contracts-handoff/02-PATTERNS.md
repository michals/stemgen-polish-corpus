# Phase 2: Source Hardening + Contracts + Handoff - Pattern Map

**Mapped:** 2026-10-16
**Files analyzed:** 4 (2 modified, 2 new docs, 1 new test)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/polish_corpus/text_sources.py` (MODIFY) | service | streaming | itself (re-pass loop `:56-66`) | exact |
| `src/polish_corpus/text_cleaning.py` (MODIFY) | utility | transform | itself (numbered pipeline steps) | exact |
| `tests/test_source_hardening.py` (NEW) | test | batch | `tests/test_cleaning.py` | role-match |
| `docs/tokenizer-contract.md` + `ground-truth-issues.md` (NEW) | docs | none | `quality-audit.md` (repo-root evidence doc) | role-match |

## Pattern Assignments

### `src/polish_corpus/text_sources.py` (service, streaming) — MODIFY

**Analog:** itself — the four `while count < max_docs` re-pass loops are byte-identical in shape.

**Dedup-guard edit:** add `import hashlib` (stdlib, groups with existing `csv/gzip/json/re` imports), then in each iterator insert the seen-set check inside the `for doc in doc_iter` body per RESEARCH §1. Same 6-line hunk × 4 iterators — copy-paste, not a shared wrapper (each loop spells `chunk_text_stream` args differently; a wrapper would obscure the per-genre `target_words`/`min_words`).

**Boilerplate edit:** module-level `_BOILERPLATE_RES` tuple + `_is_boilerplate(line) -> bool` following the `text_cleaning.py` private-helper pattern (leading underscore, PEP 257 one-line docstring, typed signature). Call site: `iter_literature_docs._paragraphs` line loop — `if _is_boilerplate(line): continue` before the existing three literal checks (which fold into the helper's substring list). Lenient-by-convention: never raise on weird lines, return False.

### `src/polish_corpus/text_cleaning.py` (utility, transform) — MODIFY

**Analog:** itself — numbered `# 1. ... # 7.` pipeline comments. URL/email strip becomes new step `# 4b` (after unescape/control-strip, before token DROP) with module-level `_URL_RE`/`_EMAIL_RE` compiled constants beside `_QUOTE_REPLACEMENTS`. Print-free, pure `str -> str`, no signature changes — `clean_text`/`tokenize`/`is_valid_token` shapes unchanged.

### `tests/test_source_hardening.py` (test, batch) — NEW

**Analog:** `tests/test_cleaning.py` — plain `test_*` functions, `from polish_corpus.text_sources import ...` (`pythonpath = ["src"]`), no fixtures/classes except `tmp_path` where a writer round-trip is needed. Parametrize URL/email drop-retain cases and WL boilerplate table; one dedup test with a stub paragraph generator + small `max_docs`.

---

## Shared Patterns

### Module docstring / logging / error handling
Same as Phase 1 PATTERNS: one-line-summary docstrings, zero logging in pure functions (`[Warning]` prints stay in builder orchestration), lenient `errors="replace"` + skip-and-continue preserved.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| URL/email regexes | — | — | No in-repo precedent — follow RESEARCH.md §2 verbatim (simple classes, no nested quantifiers). |
| Contract/handoff markdown | docs | none | Follow `quality-audit.md` evidence style: claim + file:line + example. |

## Metadata

**Analog search scope:** `src/polish_corpus/`, `tests/`
**Files scanned:** 4 (`text_sources.py`, `text_cleaning.py`, `corpus_sampler.py`, `test_cleaning.py`)
**Pattern extraction date:** 2026-10-16
