---
phase: 01-cleaning-stage-shared-tokenizer
verified: 2026-10-16T00:00:00Z
status: passed
score: 6/6 must-haves verified
covered_files:
  - src/polish_corpus/text_cleaning.py # sha256:7bf4a1bc4ed7c5d01a21323fc39e2c98d9b44230e459053713d3efcc15ac808d
  - src/polish_corpus/corpus_sampler.py # sha256:b03d3504f3e408d3e54d35b9a5f7291277090f82487b26621b08deacb90e028d
  - tests/test_cleaning.py # sha256:7a9cb01f0040fd8d98de7d577588f2806b9f7d671b21e1cc849d7fcf6320fc3a
covered_digest: "unavailable: verification.fingerprint verb not implemented in this environment (sdk_unknown_command); per-file sha256 recorded inline above"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 01: Cleaning Stage + Shared Tokenizer Verification Report

**Phase Goal:** Corpus text is cleaned through a single shared stage so stored docs and TF/DF counts contain only valid Polish tokens
**Verified:** 2026-10-16
**Status:** passed
**Re-verification:** No — initial verification (includes post-review fix commits 0ccc2e5, 824b940, 6adda97, 9a8ad54)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Stored doc text and TF/DF counts derive from the same cleaned text (re-tokenizing a stored doc reproduces its recorded counts) | ✓ VERIFIED | Executed: dirty doc `Béziera café COVID-19 biało-czerwony słowo` through `BalancedCorpusWriter.add_document` → stored `'biało-czerwony słowo'`, `set(tokenize(stored)) == set(term_freq)` exact match; `add_document` line 77 cleans before both `writestr` (98) and counting (90); `tests/test_cleaning.py::test_stored_text_and_counts_agree` passes |
| 2 | Tokens with non-Polish diacritics vanish entirely (no split fragments like ziera, bner, caf in docs or counts) | ✓ VERIFIED | Executed: `tokenize(clean_text('Béziera café COVID-19 …'))` → foreign tokens gone whole, no `ziera`/`caf`/`COVID` fragments in stored text or TF; 11-case audit battery (`Schrödinger`, `Saint-Étienne-la-Geneste`, …) all pass via `test_audit_drop_fixtures_vanish_whole`; `_drop_token` kills on any non-Polish `L` char, any digit, any `M` mark |
| 3 | A quick-test build runs end-to-end with cleaning active | ✓ VERIFIED | `pytest tests/` → 47 passed, 1 skipped (includes `test_smoke.py` quick-test build with gate active); `ruff check src/ tests/` clean |
| 4 | HTML entities decode before the foreign-token check (`&eacute;` becomes `é` and is then filtered, not passed through) | ✓ VERIFIED | Executed: `clean_text('caf&eacute; test')` → `'test'` (decoded then dropped whole); `clean_text('słowo cafe&#769; inne')` → `'słowo inne'`, tokenize → `['słowo','inne']` (CR-01 fix holds: NFC → unescape → NFC → strip → filter); `test_entity_decodes_before_filter`, `test_entity_encoded_combining_mark_drops_whole`, `test_non_composable_decomposed_sequence_drops_whole` pass |
| 5 | Pure-numeric and alphanumeric tokens (`2012`, `COVID-19`, `model3`) are excluded from TF/DF while valid Polish (incl. `biało-czerwony`) is retained | ✓ VERIFIED | Executed: `tokenize(clean_text('2012 model3 słowo'))` → `['słowo']`; `tokenize('biało-czerwono-zielony')` → whole + `is_valid_token` True (WR-02 fix holds: `(?:-…)*`); exclusion enforced in both `clean_text` (`_drop_token` digit check) and `is_valid_token` (digit + per-segment checks); `test_numeric_tokens_excluded_from_counts`, `test_hyphen_per_segment_validation`, `test_multi_hyphen_compound_retained_whole` pass |
| 6 | Docs that clean down to empty never break the pipeline (flow through without corrupting quota, archive, or counters) | ✓ VERIFIED | Executed: `add_document(genre, 'Béziera café')` → returns `""`, zero doc_counts, no zip entry; `add_documents_for_genre` skips `""` without consuming quota (WR-04 fix holds); `chunk_text_stream` cleans before counting and skips foreign-only paras (WR-03 fix holds: foreign-only input yields no doc); `test_empty_after_clean_skips_write_and_quota`, `test_chunker_skips_foreign_only_paragraph` pass |

**Score:** 6/6 truths verified (0 present-but-behavior-unverified — every truth was verified by executing the code in-process, not by grep alone)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/polish_corpus/text_cleaning.py` | Sole owner of TOKEN_RE/is_valid_token/clean_text/tokenize, load-bearing ordering | ✓ VERIFIED | Exists (123 lines, substantive); ordering NFC → unescape → NFC → strip → filter → normalize → collapse with numbered comments; sole TOKEN_RE definition in `src/` (grep confirms no copies); imported by sampler |
| `src/polish_corpus/corpus_sampler.py` | Writer choke-point gate + clean-before-count chunker | ✓ VERIFIED | `add_document` line 77 `clean_text` first line, sentinel `""` on empty; chunker lines 38–43 clean-before-count; counting via shared `tokenize`; `add_documents_for_genre` quota-skip loop |
| `tests/test_cleaning.py` | Regression pins incl. review repros | ✓ VERIFIED | 19 test functions, 68 asserts, 44 passed; includes CR-01 (`cafe&#769;`, `q́x`), WR-01 (`&#0;`, `&#xFFFD;`), WR-02 (triple compound), WR-03/WR-04 pins |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `text_cleaning.clean_text` | `BalancedCorpusWriter.add_document` | first-line gate before writestr and counting | WIRED | `corpus_sampler.py:77`; executed end-to-end, agreement exact |
| `corpus_sampler` counting | shared `tokenize` | `count_words` delegates; writer line 90 tokenizes cleaned text | WIRED | No local TOKEN_RE; `from .text_cleaning import clean_text, tokenize` (line 17) |
| `html.unescape` | foreign-token DROP | positioned before filter with re-NFC between | WIRED | Lines 93–97; executed entity + NFD-entity repros drop whole |
| numeric exclusion | both `clean_text` and `is_valid_token` | digit checks in `_drop_token` (line 45) and `is_valid_token` (line 66) | WIRED | Executed via both paths; docs and counts agree |
| `chunk_text_stream` | `clean_text` | clean-before-count (lines 38–43) | WIRED | Executed: foreign-only para skipped, sizing on cleaned counts |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `corpus_sampler.add_document` | `tokens` (line 90) | `tokenize(clean_text(text))` — real cleaned pipeline text | Yes — executed: `['biało-czerwony','słowo']` counted and stored | ✓ FLOWING |
| `corpus_sampler.chunk_text_stream` | `para_clean` (line 38) | `clean_text(para.strip())` per paragraph | Yes — executed: foreign-only para yields nothing, Polish para flows | ✓ FLOWING |
| `corpus_sampler.add_paradigm_batch` | `tokens` (line 130) | `[t.lower() for t in forms]` direct, not via `tokenize` | Accepted by design (IN-02, plan-scoped out; forms pre-validated by VALID_WORD_RE) | ✓ FLOWING (documented bypass) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 entity-combining repro drops whole | `tokenize(clean_text('słowo cafe&#769; inne'))` | `['słowo','inne']` | ✓ PASS |
| CR-01 non-composable `q́x` drops whole | `clean_text('słowo q́x inne')` | `'słowo inne'` | ✓ PASS |
| WR-01 encoded strips stay stripped | `clean_text('słowo &#0; inne')`, `&#xFFFD;` | both `'słowo inne'` | ✓ PASS |
| WR-02 triple compound whole + valid | `tokenize('biało-czerwono-zielony')`, `is_valid_token(…)` | `['biało-czerwono-zielony']`, `True` | ✓ PASS |
| Stored/count agreement | writer round-trip, `set(tokenize(stored)) == set(term_freq)` | exact match | ✓ PASS |
| Empty-after-clean sentinel | `add_document(genre,'Béziera café')` | `""`, zero counters, no zip entry | ✓ PASS |
| Chunker skips foreign-only para | `chunk_text_stream(iter(['Béziera café', <polish>]))` | only Polish doc yielded | ✓ PASS |
| Full suite + lint | `pytest tests/ -q`, `ruff check src/ tests/` | 47 passed 1 skipped; clean | ✓ PASS |

### Probe Execution

No probes declared by plans and no `scripts/*/tests/probe-*.sh` in repo (pure-Python pipeline, no scripts/ dir). Section not applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CLN-01 | 01-01 | clean_text stage before archive write AND TF/DF counting | ✓ SATISFIED | Writer gate line 77 + chunker clean-before-count lines 38–43; executed agreement |
| CLN-02 | 01-01 | Polish-only policy, no split fragments in docs or counts | ✓ SATISFIED | `_drop_token` whole-token DROP; 11-case audit battery green; executed spot-checks |
| CLN-03 | 01-02 | Entities unescaped BEFORE foreign-token check | ✓ SATISFIED | Lines 93–97 ordering; `&eacute;`/NFD/entity-combining pins green; executed repros |
| TOK-01 | 01-01 | Single shared TOKEN_RE + is_valid_token used for all counting | ✓ SATISFIED | Sole owner module; no TOKEN_RE copies in src/; `count_words` + writer delegate to `tokenize` (paradigm path documented bypass IN-02, plan-scoped) |
| TOK-02 | 01-02 | Numerics/alphanumerics excluded from TF/DF | ✓ SATISFIED | Dual enforcement (`_drop_token` + `is_valid_token`); numeric battery green |

All 5 phase requirement IDs accounted for (01-01 claims CLN-01/02 + TOK-01; 01-02 claims CLN-03 + TOK-02 — union is exactly the roadmap Phase 1 set). Remaining REQUIREMENTS.md IDs (TOK-03, SRC-01–03, VER-01–03, DOC-01) map to Phases 2–3 per traceability table — none orphaned.

### Anti-Patterns Found

None. Scanned `text_cleaning.py`, `corpus_sampler.py`, `test_cleaning.py` for TBD/FIXME/XXX/TODO/PLACEHOLDER/placeholder/stubs — zero matches. No `return null/[]/{}` stubs, no console.log-only handlers, no hardcoded empty props. `summary()` `dict[str, any]` annotation (IN-01) is a cosmetic typing note explicitly accepted as no-action in the disposition — not a blocker.

### Review-Fix Regression Verification

Every CR/WR fix from 01-REVIEW.md was re-verified by executing the current code (not by trusting commit messages):

| Finding | Fix commit | Re-executed check | Holds |
|---------|-----------|-------------------|-------|
| CR-01 combining-mark salvage | 0ccc2e5 | `cafe&#769;` → `['słowo','inne']`; `q́x` → dropped | Yes |
| WR-01 reintroduced strips | 0ccc2e5 | `&#0;` / `&#xFFFD;` → `'słowo inne'` | Yes |
| WR-02 single-hyphen split | 824b940 | triple compound whole, validator agrees | Yes |
| WR-03 chunker fragment counts | 6adda97 | foreign-only para skipped; sizing on cleaned text | Yes |
| WR-04 empty docs consume quota | 9a8ad54 | `""` sentinel, no write/counters/quota | Yes |

Note: `count_words('Béziera café')` on *raw* text still returns fragment counts (3) — this is not a defect: all in-pipeline callers clean first (chunker line 38→41), and the writer counts post-gate text. WR-03's fix (clean before counting at call sites) is what was required and holds.

### Human Verification Required

None. All truths are pure-function pipeline properties verified by execution; no visual, real-time, UX, or external-service behavior involved. Full-tier rebuild gate (zero foreign fragments at scale) belongs to Phase 3 (VER-02), not this phase.

### Gaps Summary

No gaps. All 6 must-have truths verified against the actual codebase with executed behavioral evidence; all 5 phase requirements satisfied with traceability closed; review findings fixed and re-proven; suite 47 passed / 1 skipped, ruff clean.

---

_Verified: 2026-10-16_
_Verifier: the agent (gsd-verifier)_
