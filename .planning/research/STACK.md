# Stack Research

**Domain:** Polish corpus text cleaning / tokenizer alignment / ground-truth hygiene (Python)
**Researched:** 2026-10-16
**Confidence:** HIGH (stdlib behavior verified from official docs + repo audit evidence; MEDIUM on "no new dependency needed" judgment for scale — validated by full-tier rebuild in Phase D)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python stdlib `unicodedata` (`normalize`, `is_normalized`, `category`) | stdlib, Python >=3.10 (repo floor) | NFC enforcement + control-char / combining-mark detection | Canonical tool for exactly this job; NFC is the Unicode-recommended form for general text. Audit scanned 84k WikiNeural tokens and found 0 non-NFC, but enforcement is one line (`unicodedata.normalize("NFC", text)`) with zero dependency cost and prevents decomposed `e + ◌́` from slipping past the tokenizer. `category()` (`Cc`, `Cf`, `Cs`, `Co`, `Cn`, `Me/Mn`) is the standard way to strip controls without hand-rolled blocklists. |
| Python stdlib `re` (compiled patterns, module-level constants) | stdlib | `TOKEN_RE` / `is_valid_token()` / foreign-letter detection / quote-dash normalization | The Polish valid-token alphabet is a **closed, enumerable set** (`a-zA-Z` + `ąćęłńóśźż` + case variants + single internal hyphen). stdlib `re` handles this with no gaps — confirmed by CPython docs. A single shared compiled `TOKEN_RE` + `is_valid_token()` imported by `corpus_sampler.py`, `morfeusz_extractor.py`, and `builder.py` fixes the audit's Issue #4 (sampler splits while `VALID_WORD_RE` rejects). Keep patterns as module constants so stemgen can copy the documented regex verbatim. |
| Python stdlib `html.unescape` | stdlib | Decode `&oacute;` / `&#380;` entities in news CSV (`text_sources.py:109-116`) and WikiNeural (`text_sources.py:135-151`) before cleaning | Audit Issue #7: the news path assumes `row[1]` is clean. `html.unescape` is the stdlib-correct fix — zero new deps, handles both named and numeric entities. Apply before NFC so decoded chars normalize correctly. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pyarrow` | >=14.0.0 (already in `pyproject.toml`) | Parquet GT export + audit-stat columns | Already the GT I/O layer (`benchmark_splitter.export_records_to_parquet`). Add `oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate` as `build_summary.json` fields (plain JSON, no schema change) — no new library needed. |
| `pytest` (+ stdlib `parametrize`) | >=8.0.0 (already in dev deps) | Regression tests with audit fixture table | Already the test runner (`tests/test_smoke.py` is the only test today). Add `tests/test_text_cleaning.py` with `@pytest.mark.parametrize` over the audit §2 table (`Béziera`, `Schrödinger`, `Saint-Étienne-la-Geneste`, `café`, `COVID-19`, `Linköping`, …) asserting token output + GT-row absence. No fixture library (factory-boy, hypothesis) needed — the table is fixed ground truth, explicit cases beat generative tests here. Optional: `hypothesis` text strategies only if fuzzing `clean_text()` idempotence later — defer. |
| `ruff` | >=0.8.0 (already in dev deps) | Lint the new `text_cleaning.py` module | No change; keep line-length 100 per existing config. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `unicodedata.is_normalized("NFC", s)` spot-checks in tests | Assert NFC postcondition on cleaned fixtures | Cheap invariant test: `assert is_normalized("NFC", clean_text(s))` for each fixture row. |
| Repo `.venv` Python for audit rescans | Reproduce foreign-letter frequency scans per source | Audit reproduction notes use repo venv against `data_cache/`; reuse the same scan script post-fix to prove zero fragments after the full-tier rebuild. |

## Installation

```bash
# Core — no new runtime dependencies. Stdlib only:
# unicodedata, re, html (Python >=3.10, already required)

# Existing (unchanged)
pip install pyarrow>=14.0.0

# Dev dependencies (unchanged)
pip install -D pytest>=8.0.0 ruff>=0.8.0
```

New module placement: `src/polish_corpus/text_cleaning.py` with `clean_text()`, `is_valid_token()`, `TOKEN_RE`, `FOREIGN_LETTER_RE`, `DIGIT_TOKEN_RE` — imported by `corpus_sampler.py` (replacing its local `TOKEN_RE` at line 20 and raw `writestr` at line 91) and `morfeusz_extractor.py` (replacing `VALID_WORD_RE` at line 23). `builder.py:209-211` imports the OOV-drop policy from the same module.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| stdlib `re` with explicit Polish class `[a-zA-Ząćęłńóśźż…]` | Third-party `regex` module (`\p{Script=Latin}`, `\p{L}`) | Only if the project reverses the strict Polish-only decision and needs script-aware matching (e.g. keep French/German tokens but tag them). For drop/flag semantics on a closed alphabet, `regex` adds a compiled dependency for zero behavioral gain. Revisit iff stemgen requests script metadata. |
| Explicit foreign-letter set check (`éèüöçčñø…` via set difference against allowed alphabet) | Language ID (`fasttext` lid.176, `langdetect`, `lingua`) | Per-sentence/per-doc language ID is 100–1000× heavier, nondeterministic across versions, and wrong-grained: the bug is *token-level* fragments inside otherwise-Polish sentences (`Béziera` in a Polish wiki article). Character-set validation is deterministic, O(n), explainable, and matches the "strict Polish-only" Key Decision in PROJECT.md. Use lang ID only if a future phase adds whole-document foreign-language routing — out of scope (A–D). |
| `unicodedata.normalize("NFC", …)` | `ftfy` / `clean-text` / NFKC normalization | `ftfy` fixes mojibake; the audit found none (sources are UTF-8 with `errors="replace"`). `clean-text` bundles aggressive lowercasing/transliteration that would destroy the case signal `morfeusz_extractor.py:91` depends on (proper-noun filter runs *before* lowercasing). NFKC folds compatibility chars (`ﬁ→fi`, `²→2`) — undesirable for a stemmer-training corpus where surface fidelity matters; NFC preserves canonical equivalence only. |
| Hand-rolled `QUOTE_MAP` / `DASH_MAP` dicts + `str.translate` | `unidecode` transliteration | `unidecode` would transliterate `café→cafe`, creating *false Polish tokens* — the opposite of the hygiene goal. Normalization here means `„ ” « »→"` and `— –→-` via explicit maps, then foreign-diacritic tokens are dropped, not ASCII-folded. |
| `str.casefold` avoided; keep `.lower()` | `casefold()` for case-insensitive matching | Turkish/German `casefold` expansions (`ß→ss`) would create tokens that never appear in surface text, breaking the stored-doc/TF/DF agreement constraint. Keep `.lower()` as today. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `regex` PyPI package | Extra dependency; `\p{…}` script properties solve a problem this project decided away (strict Polish-only closed alphabet). Adds build/binary surface for no behavioral gain. | stdlib `re` + explicit character class |
| `fasttext` / `langdetect` / `lingua` | Token-level noise needs character validation, not sentence classification; model downloads break hermetic builds and add nondeterminism to `build_summary.json` audit stats. | `FOREIGN_LETTER_RE` set-difference check in `text_cleaning.py` |
| `ftfy`, `clean-text` | Mojibake fixing not evidenced; bundled lowercasing/transliteration conflicts with Morfeusz proper-noun-before-lowercase ordering. | `unicodedata.normalize("NFC")` + explicit control-char strip |
| NFKC normalization | Compatibility folding (`²→2`, `ﬁ→fi`) mutates surface forms the stemmer must see verbatim. | NFC only |
| `unidecode` / ASCII-folding | Converts foreign noise into plausible-looking Polish tokens (`café→cafe`), hiding the exact pollution the project must eliminate. | Drop/flag foreign-diacritic tokens per strict policy |
| New numeric-parsing libs (`phonenumbers`, date parsers) | Digit policy is "drop pure-numeric and alphanumeric tokens from TF/DF" — a regex test (`\d` presence), not parsing. | `DIGIT_TOKEN_RE` + counter in `build_summary.json` (`digit_token_rate`) |
| `hypothesis` (now) | Fixed audit table is the ground truth; property tests add setup cost before the deterministic fixtures exist. | `pytest.mark.parametrize` over audit §2 table; add hypothesis later only for `clean_text` idempotence fuzzing |

## Stack Patterns by Variant

**If performance audit shows cleaning is the bottleneck on full-tier builds:**
- Keep the same stdlib stack; precompile all patterns at module import, process line-by-line (generators already stream in `text_sources.py`), and batch `Counter.update` per doc as `corpus_sampler.py:88-89` does today. No C-extension tokenizer (e.g. `tokenizers`, `blis`) is warranted — cleaning is O(n) regex/sub work dominated by I/O.

**If stemgen requests the shared tokenizer as a published contract:**
- Expose `text_cleaning.TOKEN_PATTERN_STR` (plain string) plus the compiled `TOKEN_RE` so the stemgen repo (separate owner, out of scope) can vendor the identical pattern in its own language/stack without importing this package.

**If a future milestone re-admits foreign names (reversing strict Polish-only):**
- Then — and only then — evaluate the `regex` module for `\p{Script}` tagging and `fasttext` for doc-level routing. Do not pre-install either now.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| stdlib `unicodedata` | Python >=3.10 (repo floor) | Unicode version tracks the interpreter; NFC semantics stable across 3.10–3.13 for the Latin + Polish range. Pin nothing. |
| stdlib `re` / `html` | Python >=3.10 | No version risk. |
| `pyarrow>=14.0.0` | Python >=3.10 | Already declared; audit-stat additions are JSON-side, no parquet schema bump unless OOV `lemma=NULL` option is chosen (then version the schema explicitly per PROJECT.md compatibility constraint). |
| `pytest>=8.0.0`, `ruff>=0.8.0` | dev only | Already declared; no change. |

## Sources

- CPython docs: `re` (notes third-party `regex` as the fuller-Unicode alternative — deliberately declined above), `unicodedata.normalize/is_normalized` (NFC/NFKC semantics) — HIGH confidence (official docs).
- Unicode FAQ on normalization (NFC best for general text; NFKC for identifiers/security) — HIGH; corroborates NFC-over-NFKC choice — HIGH (cross-checked).
- Repo evidence: `src/polish_corpus/corpus_sampler.py:20` (`TOKEN_RE`), `:73-91` (raw `writestr` + split counting), `src/polish_corpus/text_sources.py:27,77,111,141` (`errors="replace"` → `�` source; `:40-41,149-150` partial punctuation fix; `:56-66,90-100,122-132,154-164` re-pass loops), `src/polish_corpus/morfeusz_extractor.py:23` (`VALID_WORD_RE`), `:91` (proper-noun-before-lowercase ordering constraint), `src/polish_corpus/builder.py:209-211` (OOV self-lemma fallback), `pyproject.toml` (requires-python >=3.10, pyarrow/pytest/ruff pins), `tests/test_smoke.py` (existing test surface) — HIGH (read directly).
- `quality-audit.md` §§2–4 (truncation table, per-source foreign-letter frequencies, 0 non-NFC on 84k tokens, ranked issues) — HIGH (repo primary source, verified against current `TOKEN_RE`).

---
*Stack research for: Corpus Quality Hardening (stemgen-polish-corpus)*
*Researched: 2026-10-16*
