# Feature Research

**Domain:** Corpus cleaning / validation for a Polish stemmer-training corpus (hardening pass on an existing pipeline, not a greenfield corpus build)
**Researched:** 2026-10-16
**Confidence:** HIGH for table-stakes judgments (convergent across OSCAR/CulturaX/Dolma/FineWeb/CCNet/ROOTS pipelines + audit evidence); MEDIUM for complexity estimates (codebase-specific, unverified at full-tier scale)

## Feature Landscape

Production corpus pipelines converge on the same cleaning/validation stack. CulturaX (language ID → URL filtering → metric-based cleaning → document refinement → MinHash dedup), Dolma (CCNet language filtering → URL/doc dedup → quality/content filtering → paragraph dedup), FineWeb/CCNet (language ID, boilerplate removal, line-length and repetition filters, dedup), and the `clean-text`/`ftfy` canon (NFC, mojibake/HTML-entity repair, control-char stripping, quote/dash normalization) all implement the same layers. For *this* project the question is not "what exists" but "which layer is table stakes for a Polish stemmer-training corpus where a single foreign diacritic becomes a garbage training row." The audit answers it: anything that lets `é/ü/ö/ç/č/ñ/ø` fragments, `(word, word)` identity rows, or digit-truncation artifacts into `ground_truth.parquet` is table stakes to fix. Everything else is a differentiator or deferred.

### Table Stakes (Missing These = Corpus Feels Broken / Stemmer Trains on Garbage)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `clean_text()` normalization stage (NFC → strip `�`/control chars → quote/dash normalization → whitespace collapse) | Every production pipeline normalizes before counting; audit §4.3 found no normalization stage, so stored docs and TF/DF can disagree | LOW | New `text_cleaning.py` (or in `corpus_sampler.py`); `unicodedata.normalize("NFC")`, strip `\ufffd` + Cc/Cf categories, map `„ " « » → "`, `— – → -`. Must run **before** both `writestr` and `TOKEN_RE` counting (audit Phase A). Pure-Python, streaming-safe. |
| Strict Polish-only foreign-token policy (drop tokens/sentences with non-Polish diacritics) | Audit's decided policy (PROJECT.md Key Decisions): `Béziera→B+ziera`, `café→caf` fragments become GT rows. Lenient "keep surface, exclude from TF/DF" reintroduces the doc/count disagreement the project exists to kill | LOW | Token-level drop is the minimum; sentence-level drop for foreign-dense Wikipedia passages is the recommended extension (WikiNeural is the worst offender: `é×43, è×16, ö×14…` + Cyrillic). Resolves audit open decision #1 in favor of strict. |
| Single shared tokenizer/validator (`TOKEN_RE` + `is_valid_token()` used by sampler, GT export, documented for stemgen) | Audit §4.4: `VALID_WORD_RE` *rejects* foreign forms while `TOKEN_RE` *splits* them — vocabularies diverge by design. Two tokenizers = two truths | LOW | One import, three consumers. Also the contract stemgen consumes; document it. Prerequisite for every counting/hygiene feature below. |
| OOV ground-truth hygiene: drop tokens with no Morfeusz lemma (no silent `(word, word)` identity rows) | Audit §4.1 (ranked high): `builder.py:209-211` fallback teaches stemgen identity mappings for noise. This is the highest-leverage GT feature | LOW | `morfeusz.dominant_lemma.get(word)` miss → skip row. Resolves audit open decision #2 in favor of drop (the `lemma=NULL + oov_flag` variant is a schema change — see anti-features). |
| Numeric-token policy: exclude pure-numeric and alphanumeric tokens from TF/DF | Same bug class as diacritics (`COVID-19→COVID`, `model3→model` truncation); 20/21 test-build docs contain digit tokens, so this is not theoretical | LOW | Drop pure-numeric; drop/strip alphanumeric from TF/DF. Record counts in `build_summary.json`. Decided in PROJECT.md; no owner input still needed. |
| Quote/dash/punctuation normalization (`„ " « » — –`) | Polish text is full of `„…"` quotes and `—/–` dashes; without it the same word tokenizes differently by source, and stemgen's tokenizer disagrees with ours | LOW | Fold into `clean_text()`; trivially testable. Part of audit Phase A. |
| `�`/control-char stripping + NFC enforcement | `errors="replace"` in all four `iter_*_docs` readers can inject `�`; NFC scan was clean at 84k tokens but unguarded at full-tier scale | LOW | `unicodedata.normalize("NFC")` + strip `\ufffd`, Cc/Cf. Zero behavioral risk. |
| Regression tests with the audit fixture table (`Béziera`, `Schrödinger`, `Saint-Étienne-la-Geneste`, `café`, `COVID-19`, …) | Audit §2 table is already verified against current `TOKEN_RE` — it is a free, pre-built fixture set. No fixture table = the exact bug class regresses silently | LOW | Unit tests on `clean_text()` + tokenizer + GT export. Highest ROI per line of test code in the project. |
| Audit stats in `build_summary.json` (`oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`) | PROJECT.md Core Value is validated by "audit stats showing zero foreign fragments" — without these counters the full-tier rebuild proves nothing | LOW–MEDIUM | Wire counters through `BalancedCorpusWriter.summary()`; the rates, not raw counts, are the acceptance signal. |
| Full-tier rebuild verification (zero foreign fragments) | `output/general/` is a 21-doc seed-dominated test build; all audit evidence is from 3k-sample scans. Unit tests alone cannot prove corpus-scale cleanliness (PROJECT.md Key Decisions) | MEDIUM | Not a feature per se but the acceptance gate for all of the above; needs a real tier build, which is compute/time cost, not code cost. |

### Differentiators (Competitive Advantage — Valuable Here, Not Universal)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-source foreign-density handling (strict sentence-drop for WikiNeural, token-drop elsewhere) | WikiNeural is an order of magnitude dirtier than literature (`é×43…` + Cyrillic vs `ö×1`); uniform policy either over-drops clean genres or under-cleans Wikipedia | MEDIUM | Foreign-fragment *rate per genre* in `build_summary.json` tells you whether this is needed. Start uniform (table stakes), add per-source thresholds only if Wikipedia still leaks. |
| Stronger Wolne Lektury boilerplate filtering (headers/footers, `Rozdział` markers, page numbers) | Literature is currently the cleanest genre, so this buys less than foreign-token work — but 19th-c. novels (e.g. `Lalka`) contain French dialogues/quotations that surface at full scale | LOW–MEDIUM | Extend the `Ten utwór…/ISBN/Wolne Lektury` line filters with header/footer and chapter-marker patterns. Audit Phase D; opportunistic, do after A–C. |
| HTML-unescape + markup/URL stripping for news/wiki paths | News CSV path assumes `row[1]` is clean; currently true in sample, unguarded at scale. `html.unescape` + tag/URL stripping is one function | LOW | `html.unescape()` first (never skip — entities like `&oacute;` decode to foreign diacritics that must then hit the Polish-only filter *after* unescaping; order matters), then strip tags/URLs. Cheap insurance. |
| `iter_*_docs` dedup guard (content-hash `seen` set, fail instead of re-yielding) | Re-pass `while count < max_docs` loops re-create generators and re-chunk small sources → duplicate docs, skewed DF. DF skew silently mistrains stemmer frequency priors | LOW | `hash(text)` seen-set per iterator; streaming-safe (hashes, not docs). Audit §4.6; do it — it is cheap and DF correctness depends on it. Highest value-for-effort item in Phase D. |
| Proper-noun-like OOV filtering/flagging at GT export | Proper nouns are filtered from the *dictionary* but not from *corpus text* (audit §4.1); capital-initial OOV tokens are mostly names, not inflectional signal | LOW–MEDIUM | Heuristic (uppercase-initial + OOV → drop/flag) risks dropping sentence-initial valid words; needs the shared tokenizer + lowercase-aware check to be safe. Consider only if OOV rate stays high after the drop-OOV fix. |
| Metric-based quality filters (stopword ratio, short-line ratio, doc-length floors à la CulturaX/ROOTS) | Production pipelines use IQR-thresholded metric filters to kill boilerplate/non-prose at scale. Our genres are curated (NKJP, Wolne Lektury, news, WikiNeural), not Common Crawl, so value is lower — but Wikipedia benefits | MEDIUM | Defer until audit stats show non-prose leakage. Curated sources make this a v1.x optimization, not v1 scope. |
| Language-ID confidence per document (FastText, à la OSCAR/CulturaX) | Would catch whole foreign-language passages (French dialogues in `Lalka`, German quotes in NKJP) that token-level filters only shred into fragments | MEDIUM | Heavy dependency (FastText model) for a problem the strict Polish-only filter already bounds: fragments get dropped either way. Only worth it if sentence-level foreign passages survive cleaning and pollute docs. v1.x at earliest. |
| Fuzzy/MinHash dedup (document or paragraph level) | Standard in CulturaX/Dolma because web crawls duplicate heavily. Our sources are quasi-static dumps, not crawls; exact-hash dedup covers the known re-pass bug | MEDIUM–HIGH | Do exact-hash first (table-stakes-adjacent, cheap). MinHash only if cross-source near-dupes show up in DF analysis. Likely never needed. |

### Anti-Features (Seem Good, Avoid)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Lenient foreign-text policy (keep surface form in doc, exclude from TF/DF, optionally flagged) | "Don't throw away data" — preserves raw text fidelity | Reintroduces the exact doc/count disagreement the project exists to eliminate; stored docs would contain tokens TF/DF and GT deny, and stemgen's tokenizer would re-truncate them. Audit open decision #1 must stay strict. | Strict drop; revisit only if genre-loss stats show unacceptable Wikipedia attrition. |
| `lemma=NULL + oov_flag` GT rows instead of dropping OOV | "Keep the signal, let stemgen decide" — feels less destructive | Changes the `word, lemma, tf, df` parquet schema stemgen consumes (PROJECT.md compatibility constraint: schema stays unless explicitly versioned); pushes the hygiene burden to the consumer, which already learned identity mappings once. | Drop OOV rows in v1; schema-versioned nullable-lemma export is a future cross-repo negotiation, not a hardening-pass unilateral change. |
| Transliteration/ASCII-folding of foreign names (`Bézier→Bezier`) | "Salvage foreign tokens instead of dropping" | Creates fake Polish-looking tokens with no Morfeusz lemma → they become OOV → dropped anyway, or worse, collide with real words. Non-Polish support is explicitly out of scope. | Drop. No folding, no unidecode. |
| Full language-ID / perplexity-gated pipeline (FastText + KenLM à la CulturaX) | "Do what the big pipelines do" | Order-of-magnitude overkill for four curated Polish sources; adds model dependencies and threshold-tuning burden to fix what a character-class filter already fixes deterministically. | Deterministic Polish-alphabet validator + per-genre audit rates. Add metric filters only on evidence. |
| New genres, data sources, or non-Polish support | Corpus expansion sounds like progress | Explicitly out of scope (PROJECT.md): this is a quality pass, not expansion. New sources add unaudited noise vectors. | Freeze sources; harden the four existing ones. |
| Stemmer-side fixes in this repo | "Fix it where it hurts" | Separate repo/owner (stemgen); corpus project only fixes its inputs. Coupling them blocks the rebuild verification on external changes. | Document the shared tokenizer contract for the stemgen side; fix corpus here. |

## Feature Dependencies

```
clean_text() normalization
    └──requires──> shared TOKEN_RE + is_valid_token()
                        └──requires──> (nothing — greenfield in text_cleaning.py)
                                └──consumed-by──> sampler TF/DF counting
                                └──consumed-by──> GT export filtering
                                └──consumed-by──> stemgen contract docs

strict Polish-only foreign policy
    └──requires──> clean_text() ordering (HTML-unescape BEFORE foreign check)
    └──requires──> shared tokenizer (drop decision in one place)

OOV drop (no (word, word) rows)
    └──requires──> shared tokenizer (same vocab as counting)
    └──requires──> numeric policy (alphanumeric truncation creates fake OOV)

numeric-token policy
    └──requires──> shared tokenizer

audit stats (oov_self_lemma_rate, foreign_fragment_rate, digit_token_rate)
    └──requires──> all of the above (counters at each filter point)
    └──gates──> full-tier rebuild verification

HTML-unescape / URL handling ──must-run-before──> foreign-token filter
    (entities decode INTO foreign diacritics; wrong order = bypass)

dedup guard (seen-hash) ──independent──> (any order, but DF stats invalid without it)

boilerplate filtering ──independent──> (source-local, no coupling to tokenizer)
```

### Dependency Notes

- **Everything requires the shared tokenizer:** sampler counting, GT export, and audit counters must agree on what a token is, or rates are meaningless. Tokenizer alignment is the critical path — Phase B is not separable from Phase A despite the audit's lettering.
- **HTML-unescape must run before the foreign-token filter:** `&eacute;` decodes to `é`; filtering first then unescaping reintroduces the exact characters you just filtered. Order inside `clean_text()` is load-bearing.
- **Audit stats require all filters instrumented:** the three rates are counters at filter points, not a post-hoc scan. Retrofitting counters after the rebuild wastes a full-tier build cycle.
- **Dedup guard is order-independent but validity-critical:** DF numbers from a duplicated source are wrong even if every token is clean. Cheap, no coupling, do it early.
- **Lenient-foreign-policy conflicts with doc/count agreement:** these cannot coexist in one build; the strict decision forecloses the lenient variant (recorded as anti-feature, not a backlog item).

## MVP Definition

Scope anchor: PROJECT.md constrains this milestone to audit Phases A–D in one project, with schema compatibility and streaming performance as hard constraints. "MVP" here = the v1 hardening slice that makes the full-tier rebuild meaningful.

### Launch With (v1 — audit Phases A–D)

- [ ] `clean_text()` stage: NFC → `�`/control-strip → HTML-unescape → foreign-token policy → quote/dash normalization → whitespace collapse, applied before archive write AND TF/DF counting — the core fix; without it nothing else agrees
- [ ] Strict Polish-only foreign-token policy (token-drop minimum; sentence-drop for foreign-dense passages) — resolves audit open decision #1
- [ ] Single shared `TOKEN_RE` + `is_valid_token()` across sampler, GT export, stemgen docs — the correctness prerequisite
- [ ] OOV drop (no `(word, word)` identity rows) — resolves audit open decision #2; highest-leverage GT change
- [ ] Numeric policy (drop pure-numeric + alphanumeric from TF/DF) — same bug class, already decided
- [ ] `�`/control-char stripping, NFC, quote/dash normalization — folded into `clean_text()`, near-zero marginal cost
- [ ] Source hardening D-slice: HTML-unescape for news/wiki, URL handling, stronger WL boilerplate patterns, `seen`-hash dedup guard — all cheap, all order-independent
- [ ] Audit stats (`oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`, ideally per-genre) in `build_summary.json` — the acceptance instrumentation
- [ ] Regression tests from the audit §2 fixture table — the anti-regression gate
- [ ] Full-tier rebuild verification showing zero foreign fragments — the milestone acceptance criterion

### Add After Validation (v1.x — only on evidence from audit stats)

- [ ] Per-source foreign-density thresholds — trigger: Wikipedia attrition too high or leakage persists under uniform policy
- [ ] Proper-noun-like OOV heuristic — trigger: OOV rate stays high after drop-OOV fix
- [ ] Metric-based quality filters (stopword/short-line ratios) — trigger: non-prose leakage visible in audit stats
- [ ] Language-ID confidence per document — trigger: whole foreign passages survive cleaning

### Future Consideration (v2+ / likely never for this corpus)

- [ ] MinHash/fuzzy dedup — trigger: DF analysis shows cross-source near-dupes (unlikely with static dumps)
- [ ] Schema-versioned nullable-lemma GT export — trigger: cross-repo negotiation with stemgen owner; not a unilateral change
- [ ] KenLM-perplexity gating à la CulturaX — no foreseeable trigger for curated sources

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `clean_text()` normalization stage | HIGH | LOW | P1 |
| Strict Polish-only foreign policy | HIGH | LOW | P1 |
| Shared tokenizer/validator | HIGH | LOW | P1 |
| OOV drop (no identity rows) | HIGH | LOW | P1 |
| Numeric-token policy | HIGH | LOW | P1 |
| Audit stats in `build_summary.json` | HIGH | LOW–MEDIUM | P1 |
| Regression fixture tests (audit §2 table) | HIGH | LOW | P1 |
| Full-tier rebuild verification | HIGH | MEDIUM (compute) | P1 |
| Dedup guard (seen-hash) | MEDIUM–HIGH | LOW | P1 |
| HTML-unescape + URL handling | MEDIUM | LOW | P1 |
| Stronger WL boilerplate filtering | MEDIUM | LOW–MEDIUM | P2 (in-scope D, do if time) |
| Per-source foreign thresholds | MEDIUM | MEDIUM | P2 (evidence-gated) |
| Proper-noun OOV heuristic | MEDIUM | LOW–MEDIUM | P2 (evidence-gated) |
| Metric-based quality filters | LOW–MEDIUM | MEDIUM | P3 |
| Language-ID per document | LOW–MEDIUM | MEDIUM | P3 |
| MinHash/fuzzy dedup | LOW | MEDIUM–HIGH | P3 |
| Nullable-lemma GT schema change | LOW (negative w/ compat) | MEDIUM + cross-repo | P3 / anti-feature for v1 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

Note on the P1 cluster: eight of ten P1s are LOW cost. This milestone is unusually P1-dense because the audit already did the triage — Phases A–D *are* the P1 list, and the open decisions (strict Polish-only, drop OOV, drop numerics) are pre-resolved in PROJECT.md Key Decisions. Requirements-stage work should therefore focus on ordering (tokenizer first, counters wired before the rebuild), not on scope cuts.

## Competitor Feature Analysis

"Competitors" here are reference cleaning pipelines, not rival products — the project consumes their patterns.

| Feature | OSCAR / Ungoliant | CulturaX / Dolma / FineWeb | Our Approach |
|---------|-------------------|----------------------------|--------------|
| Language identification | Line-level FastText classification, short-line filter | Doc-level FastText confidence + IQR-thresholded metric cleaning; CCNet pre-filter drops ~84% of Common Crawl | Deterministic Polish-alphabet validator (stricter, cheaper, no model dep); FastText only if passages survive (P3) |
| Unicode normalization | Lenient thresholds, annotation-as-filter philosophy | NFC assumed; `ftfy`-class mojibake/HTML repair in canon | Explicit NFC + `�`/control-strip in `clean_text()`; HTML-unescape before foreign check |
| Foreign-token policy | Keep-with-annotation (downstream filters decide) | Drop outlying docs by metric thresholds | Strict drop at token/sentence level — stemmer training cannot tolerate "annotated but present" noise |
| Numeric handling | No explicit policy (web-LM pipelines keep digits) | Kept (digits are LM signal) | Drop from TF/DF — stemmer inflectional signal only; digits are truncation vectors here, the opposite of LM practice |
| OOV/identity rows | N/A (no GT export concept) | N/A | Drop — stemmer-specific hygiene with no web-pipeline analogue; the project's highest-leverage differentiator |
| Dedup | Line-level dedup tool (22.01), doc-level variants | MinHash doc-level + URL + paragraph-level | Exact content-hash seen-guard (re-pass bug); MinHash deferred — static dumps, not crawls |
| Boilerplate | Header/footer short-line filters | Boilerplate + non-prose + toxicity filters | Source-specific patterns (WL headers, news HTML) — curated sources need rules, not classifiers |
| Audit/quality stats | Quality annotations shipped with corpus | Perplexity, stopword-ratio, LID-score distributions | Three stemmer-relevant rates (`oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`) per genre — training-data acceptance metrics, not generic quality scores |

## Sources

- `quality-audit.md` (2026-10-16, repo root) — root cause, truncation fixture table (§2), per-source evidence (§3), 7 ranked issues (§4), Phases A–D (§5), open decisions (§6). Primary source; HIGH confidence.
- `.planning/PROJECT.md` — pre-resolved decisions (strict Polish-only, drop OOV, drop numerics, A–D in one project), schema-compat and streaming constraints. HIGH confidence.
- `src/polish_corpus/corpus_sampler.py`, `text_sources.py` — verified: no cleaning stage, raw `writestr` + `TOKEN_RE` counting divergence, re-pass duplication loops, unguarded news CSV path. HIGH confidence (read directly).
- CulturaX paper (Nguyen et al., LREC-COLING 2024; arXiv:2309.09400) — cleaning stages (LID → URL filtering → metric-based cleaning → document refinement → MinHash dedup), IQR thresholding, 46.48% doc removal, Polish slice stats. MEDIUM-HIGH confidence (peer-reviewed, web-verified).
- Dolma paper (arXiv:2402.00159) — CCNet pre-filter, URL/doc/paragraph dedup, quality/content filtering pipeline shape. MEDIUM confidence (web summary).
- OSCAR/Ungoliant lineage (Abadji et al. 2021, 2022) — line-vs-document classification, header/footer short-line filters, annotation-as-filter philosophy. MEDIUM confidence (web summary).
- `clean-text` (`jfilter/clean-text`, `clean.py`) / `ftfy` canon — fix_unicode (NFC/NFKC, mojibake, HTML entities), control-char stripping, quote/dash normalization ordering. MEDIUM confidence (library docs via web).

---
*Feature research for: Corpus Quality Hardening (stemgen-polish-corpus)*
*Researched: 2026-10-16*
