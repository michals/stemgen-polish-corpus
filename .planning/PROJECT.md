# Corpus Quality Hardening

## What This Is

Hardening pass on `stemgen-polish-corpus` (per `quality-audit.md`): add a real text-cleaning
stage, align tokenizers, and clean ground-truth exports so foreign diacritics and other
noise stop leaking into stemgen stemmer training. For the stemgen project (Michał), validated
by a full-tier rebuild with audit stats showing zero foreign fragments.

## Core Value

Corpus docs and ground truth contain only valid Polish word tokens — no truncated foreign
fragments training the stemmer toward garbage stems.

## Requirements

### Validated

- ✓ Multi-genre balanced corpus builder (NKJP spoken/forum, Wolne Lektury literature, news, WikiNeural Wikipedia) — existing
- ✓ Morfeusz 2 / PoliMorf ground-truth extraction with proper-noun and non-core-POS filtering — existing
- ✓ Inflectional paradigm completion for top lemmas (`99_morfeusz_paradigms/`) — existing
- ✓ 80/20 lemma-stratified holdout splits + Snowball `voc.txt` benchmark export — existing
- ✓ Tiered builds (compact / recommended / extended) with `corpus.zip` + parquet outputs — existing

### Active

- [ ] Strict Polish-only text cleaning stage (`clean_text()`) applied before archive write and TF/DF counting
- [ ] Single shared tokenizer/validator used by sampler, GT export, and documented for stemgen
- [ ] Foreign-fragment elimination: no `é/è/ü/ö/ç/č/ñ/ø/...` split artifacts (e.g. `ziera`, `bner`, `caf`) in docs or TF/DF
- [ ] OOV ground-truth hygiene: tokens with no Morfeusz lemma are dropped (no silent `(word, word)` identity rows)
- [ ] Numeric policy: pure-numeric and alphanumeric tokens (`2012`, `COVID-19`, `model3`) excluded from TF/DF
- [ ] Quote/dash/punctuation normalization (`„ ” « » — –`) and `�`/control-char stripping
- [ ] Source hardening: stronger Wolne Lektury boilerplate filtering, HTML-unescape for news/wiki, URL handling, `iter_*_docs` dedup guard
- [ ] Audit stats in `build_summary.json` (`oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`)
- [ ] Regression tests with audit fixture table (`Béziera`, `Schrödinger`, `Saint-Étienne-la-Geneste`, `café`, `COVID-19`, ...)
- [ ] Full-tier rebuild verification showing zero foreign fragments

### Out of Scope

- Stemgen stemmer changes themselves — this project only fixes its corpus inputs — why: separate repo/owner
- New corpus genres or data sources — why: quality pass, not expansion
- Non-Polish language support or transliteration of foreign names — why: strict Polish-only decision

## Context

- Brownfield: working pipeline in `src/polish_corpus/` (`text_sources.py`, `corpus_sampler.py`,
  `morfeusz_extractor.py`, `builder.py`, `paradigm_generator.py`, `benchmark_splitter.py`).
  See `.planning/codebase/` map (2026-10-16) for architecture/stack details.
- Prior analysis: `quality-audit.md` (2026-10-16) — root cause (raw-text write + `TOKEN_RE`
  truncation + OOV self-lemma fallback), per-source evidence (WikiNeural worst), 7 ranked
  issues, remediation Phases A–D. This project implements A–D.
- Key evidence: `TOKEN_RE` splits `Béziera→B+ziera`, `Schrödinger→Schr+dinger`,
  `café→caf`; fragments become `(word, word)` GT rows via `builder.py` OOV fallback.
- `output/general/` in tree is a 21-doc seed-dominated test build, not a full tier build —
  re-verify stats after a full build.

## Constraints

- **Compatibility**: ground-truth parquet schema (`word, lemma, tf, df`) stays compatible unless explicitly versioned — stemgen consumes it
- **Correctness**: stored doc text and TF/DF counts must agree (clean before both write and count)
- **Performance**: cleaning must stream (no full-corpus in-memory); full-tier builds stay practical
- **Scope**: Phases A–D only (cleaning, tokenizer, GT hygiene, source hardening)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Strict Polish-only: drop tokens/sentences with non-Polish diacritics | Prevent fragment generation at the source; matches Polish-stemmer training goal | — Pending |
| Drop OOV rows (no `(word, word)` identity GT) | Self-lemma rows teach stemgen identity mappings for noise | — Pending |
| Drop pure-numeric/alphanumeric tokens from TF/DF | `COVID-19→COVID` truncation is the same bug class as diacritics | — Pending |
| Scope A through D in one project | Audit phases are interdependent (cleaning + counting + GT must agree) | — Pending |
| Verify via full-tier rebuild + audit stats | Unit tests alone can't prove zero fragments at corpus scale | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-16 after initialization*
