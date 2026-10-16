# Project Research Summary

**Project:** stemgen-polish-corpus — Corpus Quality Hardening
**Domain:** Polish stemmer-training corpus cleaning / tokenizer alignment / ground-truth hygiene (Python)
**Researched:** 2026-10-16
**Confidence:** HIGH

## Executive Summary

This is a hardening pass on an existing streaming Polish corpus pipeline (`text_sources.py` → `corpus_sampler.py` → `builder.py`), not a greenfield build. Production corpus pipelines (CulturaX, Dolma, FineWeb/CCNet, OSCAR) converge on the same cleaning layers — NFC normalization, control-char stripping, quote/dash normalization, language/character filtering, dedup — but for a stemmer-training corpus the stakes are sharper: a single foreign diacritic (`Béziera` → `B` + `ziera`) becomes a garbage vocabulary entry with TF/DF counts and a ground-truth row that teaches stemgen an identity mapping for noise.

The recommended approach is unanimous across all four research tracks: create one new pure-function module `text_cleaning.py` (stdlib only: `unicodedata` + `re` + `html`) owning `clean_text()`, `TOKEN_RE`, and `is_valid_token()`; enforce cleaning at a single choke point (top of `BalancedCorpusWriter.add_document`, rebind-once so stored docs and TF/DF agree by construction); fix GT export to drop OOV/invalid rows instead of `(word, word)` fallback; harden the four source generators (HTML-unescape, WL boilerplate, URL handling, seen-hash dedup); and prove it with a full-tier rebuild showing zero foreign fragments plus three audit rates in `build_summary.json`. Eight of ten P1 features are LOW cost — the audit already did the triage, so roadmap work is about ordering, not scope cuts.

The key risks are half-applied fixes that reproduce the root bug with new symptoms: cleaning only one of the write/count paths (Pitfall 9), keeping two divergent tokenizers (Pitfall 10), overcorrecting into dropping valid Polish (Pitfall 3), and verifying on the 21-doc seed build instead of a full-tier rebuild. All are mitigated structurally (single clean point, shared validator module, retention fixtures, rebuild-gated acceptance) rather than by discipline.

## Key Findings

### Recommended Stack

No new runtime dependencies. The entire fix is Python stdlib on the existing >=3.10 floor, plus instrumentation of already-declared `pyarrow`/`pytest`/`ruff`. See [STACK.md](./STACK.md) for full rationale and declined alternatives (`regex`, FastText, `ftfy`, NFKC, `unidecode` — all explicitly rejected with reasons).

**Core technologies:**
- `unicodedata` (stdlib) — NFC enforcement + control-char/combining-mark detection; one-line, zero-dep, must run first in `clean_text()`
- `re` with explicit Polish class (stdlib, module-level compiled) — single shared `TOKEN_RE` + `is_valid_token()` fixing the sampler/extractor split-vs-reject divergence
- `html.unescape` (stdlib) — decode entities in news/wiki paths *before* the foreign-token filter (order is load-bearing)

### Expected Features

Convergent across OSCAR/CulturaX/Dolma/FineWeb plus audit evidence. See [FEATURES.md](./FEATURES.md).

**Must have (table stakes):**
- `clean_text()` stage (NFC → `�`/control-strip → HTML-unescape → foreign policy → quote/dash normalize → whitespace collapse), before archive write AND counting
- Strict Polish-only foreign-token policy (token-drop minimum; sentence-drop for foreign-dense passages)
- Single shared `TOKEN_RE` + `is_valid_token()` across sampler, GT export, stemgen docs
- OOV drop (no `(word, word)` identity rows) — highest-leverage GT change
- Numeric policy (drop pure-numeric + alphanumeric from TF/DF; `COVID-19` dropped whole, not truncated)
- Quote/dash/punctuation normalization, `�`/control stripping, NFC
- Regression tests from the audit §2 fixture table (`Béziera`, `Schrödinger`, `café`, `COVID-19`, …)
- Audit stats (`oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`, ideally per-genre) in `build_summary.json`
- Full-tier rebuild verification showing zero foreign fragments (acceptance gate, MEDIUM compute cost)
- `seen`-hash dedup guard in `iter_*_docs` (cheap, DF correctness depends on it)

**Should have (competitive / evidence-gated v1.x):**
- Per-source foreign-density thresholds — trigger: Wikipedia attrition/leakage under uniform policy
- Proper-noun-like OOV heuristic — trigger: OOV rate stays high after drop-OOV fix
- Stronger Wolne Lektury boilerplate filtering (in-scope Phase D, do if time)
- HTML-unescape + URL handling for news/wiki (cheap insurance, P1-adjacent)

**Defer (v2+ / likely never):**
- Metric-based quality filters, per-doc language ID, MinHash/fuzzy dedup, KenLM perplexity gating
- Schema-versioned nullable-lemma GT export (cross-repo negotiation, not unilateral)
- Anti-features to actively avoid: lenient foreign policy, transliteration/ASCII-folding, stemmer-side fixes in this repo, new genres/sources

### Architecture Approach

Single new module + thin call-site edits; streaming architecture untouched, no signature changes. See [ARCHITECTURE.md](./ARCHITECTURE.md).

**Major components:**
1. `text_cleaning.py` (NEW) — sole owner of `TOKEN_RE`, `is_valid_token()`, `clean_text()`, digit policy, audit helpers; pure functions, no I/O
2. `BalancedCorpusWriter.add_document` (EDIT, the gate) — `text = clean_text(text)` first line; write + count from cleaned text so agreement is structural
3. `text_sources.py` generators (EDIT) — per-paragraph pre-clean (chunk-sizing accuracy) + source-specific sanitize (HTML-unescape, WL boilerplate, URLs) + seen-hash dedup; source quirks stay here, never in shared `clean_text`
4. `builder.py` GT loop + `morfeusz_extractor.py` (EDIT) — drop OOV/invalid rows (copy Snowball's existing drop pattern); delete local `VALID_WORD_RE` copy
5. Reuse as-is: `benchmark_splitter.py` (reference drop-OOV pattern), `chunk_text_stream` (pure assembler, just switch to shared `tokenize`), `paradigm_generator.py`, `config.py`

Key patterns: writer-boundary enforcement gate (primary); idempotent two-layer cleaning (ingestion pre-clean for sizing + writer gate for correctness); validate-at-export for GT; source-specific sanitize stays at ingestion.

### Critical Pitfalls

Top risks from 10 documented in [PITFALLS.md](./PITFALLS.md):

1. **Split-not-drop tokenization (root bug class)** — `findall` scans past disallowed chars and returns fragments; fix with `clean_text()` before write+count, strict token-drop policy, shared `is_valid_token()`, fixture regression tests
2. **OOV self-lemma identity rows** — `.get(word, word)` teaches stemgen noise as truth; drop OOV rows, assert `oov_self_lemma_rate == 0`, grep all GT paths including Snowball/split code
3. **Over-aggressive filtering drops valid Polish** — sentence-level drops kill encyclopedic prose, hyphen rules mangle `biało-czerwony`, case-only heuristics nuke sentence-initial words; enforce strictness at token level, validate hyphen segments independently, require `capitalized + OOV + not-sentence-initial`, add retention fixtures
4. **Stored-text / counted-token disagreement** — cleaning one path only reproduces the root bug; rebind once at top of `add_document`, verify by re-tokenizing zip samples vs recorded TF/DF in rebuild verification
5. **Two diverging tokenizers + supporting traps** — `TOKEN_RE` splits while `VALID_WORD_RE` rejects; unify in one module with differential extract-vs-validate tests and publish the spec for stemgen; plus NFC-before-regex (NFD fixtures), whole-token digit drops (check fragments, not just wholes), and seen-hash dedup (hash final stored text)

## Implications for Roadmap

Based on research, suggested phase structure (follows audit Phases A–D; tokenizer work is critical path, not separable):

### Phase 1: Cleaning stage + shared tokenizer (Audit A+B fused)
**Rationale:** Everything depends on the shared validator — counters, GT export, and audit rates are meaningless until tokenizers agree; cleaning-before-count is the root fix.
**Delivers:** `text_cleaning.py` (`clean_text`, `TOKEN_RE`, `is_valid_token`, digit policy), writer-boundary gate in `add_document`, ingestion pre-clean, `morfeusz_extractor` import swap, fixture regression tests incl. retention + NFD cases.
**Addresses:** `clean_text()`, strict Polish-only policy, shared tokenizer, quote/dash/NFC/`�` handling, regression fixtures.
**Avoids:** Pitfalls 1, 3, 4, 6, 9, 10.

### Phase 2: Ground-truth hygiene (Audit C)
**Rationale:** Requires the Phase 1 validator (same vocab as counting) plus numeric policy (truncation creates fake OOV); small, high-leverage, separable once Phase 1 lands.
**Delivers:** GT loop drops OOV/invalid rows, `oov_self_lemma_rate` + `digit_token_rate` counters, grep-verified all GT paths, vocab-diff check for asymmetric proper-noun loss.
**Uses:** Shared `is_valid_token()` from Phase 1; Snowball drop-OOV pattern as reference.
**Implements:** Validate-at-export pattern; resolves open decision #2 (drop OOV).
**Avoids:** Pitfalls 2, 5, 7.

### Phase 3: Source hardening + audit instrumentation (Audit D)
**Rationale:** Order-independent and source-local — no coupling to tokenizer work, safe to parallelize or defer; but DF stats are invalid without the dedup guard, so it must land before the acceptance rebuild.
**Delivers:** HTML-unescape + markup/URL stripping (news/wiki), stronger WL boilerplate patterns, seen-hash dedup guards, `foreign_fragment_rate` + per-genre rates in `build_summary.json`.
**Addresses:** Source hardening slice, audit-stats instrumentation.
**Avoids:** Pitfall 8; closes integration gotchas (WikiNeural raw tokens, news CSV fragility).

### Phase 4: Full-tier rebuild verification (acceptance gate)
**Rationale:** Unit tests cannot prove corpus-scale cleanliness (21-doc seed build is unrepresentative); PROJECT.md mandates the rebuild as the milestone acceptance criterion.
**Delivers:** Full-tier build with all rates at zero, zip-vs-TF/DF agreement assertion, DF sanity, per-genre token-delta review; evidence-gated decision on v1.x items (per-source thresholds, proper-noun heuristic, metric filters).
**Avoids:** The "looks done but isn't" class — all 9 checklist items in PITFALLS.md.

### Phase Ordering Rationale

- **A+B fused first:** FEATURES dependency graph shows everything requires the shared tokenizer; ARCHITECTURE confirms Phase B is not separable from Phase A despite audit lettering — tokenizer alignment is the critical path.
- **GT hygiene second:** OOV drop requires the shared tokenizer (same vocab) and numeric policy (truncation creates fake OOV); it is the highest-leverage single GT change and keeps the parquet schema untouched.
- **Source hardening third/in parallel:** dedup guard and boilerplate patterns are order-independent but validity-critical for DF — cheap, no coupling, must precede the rebuild.
- **Rebuild last as gate:** counters must be wired at filter points before the build (retrofitting wastes a full-tier cycle); the "Looks Done But Isn't" checklist is the verification script.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (source hardening):** WL header/footer/chapter-marker pattern inventory needs a corpus-sample scan — extent of boilerplate leakage at full-literature scale is unmeasured.
- **Phase 4 (rebuild):** compute/time budget and tier choice for the verification build — needs sizing against available resources.

Phases with standard patterns (skip research-phase):
- **Phase 1:** NFC/`re`/`html` stdlib semantics verified from official docs; writer-gate and two-layer cleaning are settled patterns — proceed directly to planning.
- **Phase 2:** Drop-OOV copies the existing Snowball pattern in-repo — no external research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | CPython official docs + Unicode FAQ + direct repo reads; "no new dep" judgment validated by full-tier rebuild note |
| Features | HIGH | Convergent across 5+ reference pipelines + audit evidence; MEDIUM only on complexity estimates (codebase-specific, unvalidated at full-tier scale) |
| Architecture | HIGH | Verified against 7 source files with line refs; seams are 1–5 line edits, no speculative re-plumbing |
| Pitfalls | HIGH | Grounded in verified truncation table + direct source reads; NFD prevalence at full scale flagged as open measurement (MEDIUM-HIGH on that sub-point) |

**Overall confidence:** HIGH

### Gaps to Address

- **Full-tier scale validation:** all audit evidence is 3k-sample scans + 21-doc seed build; WikiNeural tail, *Lalka* French dialogues, NFD prevalence surface only at scale — handle via Phase 4 rebuild gate, not further research.
- **Per-genre attrition under strict policy:** uniform vs per-source thresholds is evidence-gated — wire per-genre rates in Phase 3, decide after rebuild stats.
- **Stemgen-side tokenizer coupling:** separate repo/owner; corpus side can only document the contract — flag for cross-repo coordination at release, do not block hardening on it.
- **Compute budget for rebuild:** tier choice + wall-time cost unmeasured — resolve during Phase 4 planning.

## Sources

### Primary (HIGH confidence)
- `quality-audit.md` (2026-10-16, repo root) — truncation fixture table (§2), per-source frequencies (§3), ranked issues (§4), Phases A–D (§5), open decisions (§6)
- Repo source reads — `corpus_sampler.py` (`TOKEN_RE:20`, `add_document:73-91`), `text_sources.py` (4 generators, re-pass loops, `errors="replace"`), `morfeusz_extractor.py` (`VALID_WORD_RE:23`, proper-noun filter `:91`), `builder.py` (GT fallback `:209-211`, seed fallback `:182`), `benchmark_splitter.py` (Snowball drop-OOV `:67-69`), `pyproject.toml`, `tests/test_smoke.py`
- `.planning/PROJECT.md` — pre-resolved decisions (strict Polish-only, drop OOV, drop numerics, A–D in one project), schema-compat + streaming constraints
- CPython docs (`re`, `unicodedata.normalize`/`is_normalized`) + Unicode FAQ on normalization (NFC for general text)

### Secondary (MEDIUM confidence)
- CulturaX paper (Nguyen et al., LREC-COLING 2024) — cleaning stages, IQR thresholding, Polish slice stats
- Dolma paper (arXiv:2402.00159) — pipeline shape (CCNet pre-filter, dedup, quality filtering)
- OSCAR/Ungoliant lineage (Abadji et al. 2021, 2022) — line-vs-document classification, header/footer filters
- `clean-text` / `ftfy` canon — fix_unicode ordering, control-char stripping, quote/dash normalization

### Tertiary (LOW confidence)
- None — no finding rests on a single low-quality source; complexity estimates are the weakest point (codebase-specific, flagged above).

---
*Research completed: 2026-10-16*
*Ready for roadmap: yes*
