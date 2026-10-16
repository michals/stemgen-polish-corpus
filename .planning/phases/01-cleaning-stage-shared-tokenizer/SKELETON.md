# Walking Skeleton — Corpus Quality Hardening

**Phase:** 1
**Generated:** 2026-10-16

## Capability Proven End-to-End

A dirty Polish corpus document (foreign diacritics, HTML entities, alphanumeric tokens) passes through one shared cleaning stage so the stored zip text and the TF/DF counters contain only valid Polish word tokens.

## Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cleaning ownership | NEW `src/polish_corpus/text_cleaning.py` owns `TOKEN_RE`, `is_valid_token()`, `clean_text()`, `tokenize()` | Single owner kills the raw-text-write + divergent-count bug class at the source |
| Gate location | First line of `BalancedCorpusWriter.add_document` (`corpus_sampler.py:73`) | Single choke point: stored docs and TF/DF derive from the same cleaned text by construction |
| Drop granularity | Token-level DROP for foreign AND alphanumeric tokens, no salvage | Preserves surrounding Polish signal; affected share too small to move stemmer quality |
| `clean_text()` ordering | NFC → strip U+FFFD/controls → `html.unescape` → token DROP → quote/dash normalize → whitespace collapse | Order is load-bearing: NFD marks evade the class test, entities must decode before filtering, filtering must precede punctuation normalization |
| Dependencies | Stdlib only (`unicodedata` + `re` + `html`) | No new supply-chain surface; pipeline is stdlib + pyarrow only |
| Untouched paths | `add_paradigm_batch`, `builder.py` GT loop, stemgen repo | Forms already clean; GT issues ship as `ground-truth-issues.md` docs in Phase 2, not code |

## Stack Touched in Phase 1

- [ ] Pipeline entry — `quick-test` build runs end-to-end with cleaning active (plan 01-01 tracer)
- [ ] Shared tokenizer — `TOKEN_RE` + `is_valid_token()` used by the sampler for all counting (plan 01-01)
- [ ] Cleaning stage — `clean_text()` with pinned ordering (`&eacute;`, NFD, control-strip cases) (plan 01-02)
- [ ] Regression pins — audit §2 fixture table (`Béziera`, `café`, `COVID-19`, `biało-czerwony`, …) green under `pytest` + `ruff check` (plan 01-02)

## Out of Scope (Deferred to Later Slices)

- Source sanitizers, Wolne Lektury boilerplate filtering, URL/e-mail handling, `iter_*_docs` dedup guard (Phase 2)
- Tokenizer reuse contract docs for the stemgen side (Phase 2, docs only — no stemgen repo changes)
- `ground-truth-issues.md` handoff (Phase 2, docs only — no GT export code changes)
- Audit rates in `build_summary.json` and full-tier rebuild gate (Phase 3)

## Subsequent Slice Plan

- Phase 2: Source generators emit sanitized, deduplicated docs; contracts and GT handoff documented.
- Phase 3: Corpus-scale cleanliness proven by fixture regression tests, audit rates, and a full-tier rebuild with zero foreign fragments.
