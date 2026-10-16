# Requirements: Corpus Quality Hardening

**Defined:** 2026-10-16
**Core Value:** Corpus docs contain only valid Polish word tokens — no truncated foreign fragments for stemgen to train on.

## v1 Requirements

Scope: this project produces clean `corpus.zip` files only. No changes to ground-truth export
code and no changes to the stemgen repo — GT issues are documented in a handoff file instead.

### Cleaning

- [x] **CLN-01**: Pipeline applies a `clean_text()` stage (NFC → strip `�`/control chars → HTML-unescape → foreign-token policy → quote/dash normalization → whitespace collapse) before archive write AND before TF/DF counting
- [x] **CLN-02**: Strict Polish-only policy drops tokens/sentences containing non-Polish diacritics (`é/è/ü/ö/ç/č/ñ/ø/…`, Cyrillic) so no split fragments (`ziera`, `bner`, `caf`) enter docs or counts
- [x] **CLN-03**: HTML entities are unescaped BEFORE the foreign-token check (order is load-bearing: `&eacute;` decodes to `é` and must then hit the filter)

### Tokenizer

- [x] **TOK-01**: A single shared `TOKEN_RE` + `is_valid_token()` (new `text_cleaning.py`) is used by the sampler for all counting — stored docs and TF/DF agree by construction
- [x] **TOK-02**: Pure-numeric and alphanumeric tokens (`2012`, `COVID-19`, `model3`) are excluded from TF/DF counts
- [ ] **TOK-03**: The shared tokenizer/validator is documented as a contract the stemgen side can reuse — documentation only, no modification of the stemgen repo

### Source Hardening

- [ ] **SRC-01**: `iter_*_docs` iterators use a content-hash seen-guard so small sources are never re-yielded (no duplicate docs, no DF skew)
- [ ] **SRC-02**: Wolne Lektury filtering extends beyond `Ten utwór…/ISBN/Wolne Lektury` to headers/footers, chapter markers, and page numbers
- [ ] **SRC-03**: News/wiki paths handle URLs and e-mail addresses (strip or exclude from counts) instead of passing them through raw

### Verification

- [ ] **VER-01**: Regression tests pin the audit §2 fixture table (`Béziera`, `Schrödinger`, `Saint-Étienne-la-Geneste`, `café`, `COVID-19`, `biało-czerwony` retention, …) against `clean_text()` and the shared validator
- [ ] **VER-02**: A full-tier rebuild verifies zero foreign fragments in docs and counts
- [ ] **VER-03**: `build_summary.json` reports corpus audit rates (`foreign_fragment_rate`, `digit_token_rate`, per-genre) as the acceptance signal

### Handoff Docs

- [ ] **DOC-01**: GT quality issues spotted during the audit (OOV `(word, word)` self-lemma fallback in `builder.py`, proper-noun leakage into counts, `oov_self_lemma_rate` proposal) are written to a dedicated `ground-truth-issues.md` for the upstream project — documented only, not implemented here

## v2 Requirements

Evidence-gated: implement only if v1 audit stats show the problem.

### Quality

- **QLT-01**: Per-source foreign-density thresholds (e.g. stricter sentence-drop for Wikipedia) — trigger: uniform policy under-cleans Wikipedia or over-drops clean genres
- **QLT-02**: Proper-noun-like OOV heuristic at count time — trigger: OOV rate stays high after cleaning
- **QLT-03**: Metric-based quality filters (stopword/short-line ratios à la CulturaX/ROOTS) — trigger: non-prose leakage visible in audit stats
- **QLT-04**: Per-document language-ID confidence — trigger: whole foreign passages survive cleaning

## Out of Scope

| Feature | Reason |
|---------|--------|
| Ground-truth export code changes (OOV drop, `lemma=NULL` rows) | Documented in `ground-truth-issues.md` for the upstream project; this milestone ships corpus files only |
| Any modification of the stemgen repo | Separate repo/owner; contract is documentation-only (TOK-03) |
| Transliteration/ASCII-folding of foreign names | Creates fake Polish tokens with no lemma; non-Polish support excluded by strict-policy decision |
| Full language-ID / perplexity-gated pipeline (FastText, KenLM) | Overkill for four curated sources; deterministic alphabet validator suffices unless evidence says otherwise |
| MinHash/fuzzy dedup | Static dumps, not crawls; exact-hash guard (SRC-01) covers the known bug |
| New genres, data sources, non-Polish support | Quality pass, not expansion — new sources add unaudited noise |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLN-01 | Phase 1 | Complete |
| CLN-02 | Phase 1 | Complete |
| CLN-03 | Phase 1 | Complete |
| TOK-01 | Phase 1 | Complete |
| TOK-02 | Phase 1 | Complete |
| TOK-03 | Phase 2 | Pending |
| SRC-01 | Phase 2 | Pending |
| SRC-02 | Phase 2 | Pending |
| SRC-03 | Phase 2 | Pending |
| VER-01 | Phase 3 | Pending |
| VER-02 | Phase 3 | Pending |
| VER-03 | Phase 3 | Pending |
| DOC-01 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-16*
*Last updated: 2026-10-16 after initial definition*
