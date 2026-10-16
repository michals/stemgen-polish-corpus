# Roadmap: Corpus Quality Hardening

## Overview

A hardening pass on the existing streaming corpus pipeline: first build the shared cleaning/tokenizer core (`text_cleaning.py` + writer-boundary gate) so stored docs and TF/DF counts agree by construction, then harden the four source generators and document the reuse contract plus ground-truth handoff, and finally prove corpus-scale cleanliness with fixture regression tests, audit rates, and a full-tier rebuild gate showing zero foreign fragments. GT export code is untouched throughout — GT issues ship as documentation only.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Cleaning Stage + Shared Tokenizer** - `clean_text()`, shared `TOKEN_RE`/`is_valid_token()`, writer-boundary gate (completed 2026-10-16)
- [ ] **Phase 2: Source Hardening + Contracts + Handoff** - Source sanitizers, dedup guard, tokenizer contract docs, ground-truth-issues.md
- [ ] **Phase 3: Verification** - Fixture regression tests, audit rates, full-tier rebuild gate

## Phase Details

### Phase 1: Cleaning Stage + Shared Tokenizer

**Goal**: Corpus text is cleaned through a single shared stage so stored docs and TF/DF counts contain only valid Polish tokens
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CLN-01, CLN-02, CLN-03, TOK-01, TOK-02
**Success Criteria** (what must be TRUE):
  1. Stored doc text and TF/DF counts derive from the same cleaned text — re-tokenizing a stored doc reproduces its recorded counts
  2. Tokens/sentences with non-Polish diacritics are dropped — no `ziera`/`bner`/`caf`-class split fragments in docs or counts
  3. HTML entities decode before the foreign-token check (`&eacute;` becomes `é` and is then filtered, not passed through)
  4. Pure-numeric and alphanumeric tokens (`2012`, `COVID-19`, `model3`) are excluded from TF/DF while valid Polish (including `biało-czerwony`) is retained

**Plans**: TBD

### Phase 2: Source Hardening + Contracts + Handoff

**Goal**: Source generators emit sanitized, deduplicated docs and downstream contracts are documented for stemgen and upstream owners
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: SRC-01, SRC-02, SRC-03, TOK-03, DOC-01
**Success Criteria** (what must be TRUE):
  1. Small sources are never re-yielded — no duplicate docs and no DF skew from iterator re-passes
  2. Wolne Lektury docs are free of headers/footers, chapter markers, and page numbers; news/wiki URLs and e-mail addresses are stripped or excluded from counts instead of passing through raw
  3. The shared tokenizer/validator is documented as a reuse contract for the stemgen side (docs only, no stemgen repo changes)
  4. `ground-truth-issues.md` exists at the repo root capturing the OOV self-lemma fallback, proper-noun leakage, and `oov_self_lemma_rate` proposal — documented only, no GT export code changes

**Plans**: TBD

### Phase 3: Verification

**Goal**: Corpus-scale cleanliness is proven by tests, audit stats, and a full-tier rebuild with zero foreign fragments
**Mode:** mvp
**Depends on**: Phase 1, Phase 2
**Requirements**: VER-01, VER-02, VER-03
**Success Criteria** (what must be TRUE):
  1. Regression tests pin the audit fixture table (`Béziera`, `Schrödinger`, `Saint-Étienne-la-Geneste`, `café`, `COVID-19`, `biało-czerwony` retention) against `clean_text()` and the shared validator — all pass
  2. `build_summary.json` reports `foreign_fragment_rate`, `digit_token_rate`, and per-genre rates as the acceptance signal
  3. A full-tier rebuild shows zero foreign fragments in docs and counts (not a seed/small build)

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute sequentially: 1 → 2 → 3 (parallelization is disabled for this project)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Cleaning Stage + Shared Tokenizer | 2/2 | Complete    | 2026-10-16 |
| 2. Source Hardening + Contracts + Handoff | 0/TBD | Not started | - |
| 3. Verification | 0/TBD | Not started | - |
