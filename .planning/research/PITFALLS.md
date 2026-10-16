# Pitfalls Research: Corpus Quality Hardening

**Domain:** Polish stemmer-training corpus cleaning (multilingual-contamination removal)
**Researched:** 2026-10-16
**Confidence:** HIGH (grounded in `quality-audit.md` primary evidence + verified `TOKEN_RE` truncation table + direct source reads of `corpus_sampler.py`, `text_sources.py`, `morfeusz_extractor.py`, `builder.py`)

## Critical Pitfalls

### Pitfall 1: Split-not-drop tokenization (the root bug class)

**What goes wrong:**
A character-class regex that lists allowed letters treats any foreign diacritic as a *split point* instead of rejecting the token. `TOKEN_RE = [a-zA-Ząćęłńóśźż...]+` turns one foreign word into two or three garbage fragments, and each fragment becomes a real vocabulary entry with TF/DF counts and a ground-truth row.

Verified truncation table (from `quality-audit.md` §2, reproduced against current `TOKEN_RE`):

| Input | Tokens produced | Downstream damage |
|---|---|---|
| `Béziera` | `B`, `ziera` | 2 garbage GT rows |
| `Schrödinger` | `Schr`, `dinger` | 2 garbage GT rows |
| `Hübner` | `H`, `bner` | single-letter `H` + fragment |
| `Führer` | `F`, `hrer` | single-letter `F` + fragment |
| `Besançon` | `Besan`, `on` | fragment + `on`, which collides with the Polish preposition/locative form `on` |
| `désintéressement` | `d`, `sint`, `ressement` | single-letter `d` + 2 fragments |
| `café` | `caf` | truncated stem — looks like a plausible Polish word, hardest to detect by inspection |
| `naïve` | `na`, `ve` | `na` collides with the high-frequency Polish preposition `na`, poisoning its TF/DF |
| `Saint-Étienne-la-Geneste` | `Saint`, `tienne-la`, `Geneste` | partial hyphen handling; leading `É` silently eaten |
| `COVID-19` | `COVID` | digit part silently dropped (same bug class, different alphabet) |
| `Turčianske` | `Tur`, `ianske` | fragments |

**Why it happens:**
Developers write an allowlist regex for "valid Polish letters" and assume anything else is *excluded*. But `re.findall` doesn't exclude — it *scans past* disallowed characters and returns the allowed runs on either side. Exclusion semantics require an explicit validation step (`is_valid_token` full-match / reject), not just extraction.

**How to avoid:**
1. Add `clean_text()` **before** both archive write and TF/DF counting (§6 order matters — see Pitfall 9).
2. Foreign-letter policy per PROJECT.md decision (strict Polish-only): drop tokens containing non-Polish diacritics (`é/è/ü/ö/ç/č/ñ/ø/…`) at cleaning time, so `TOKEN_RE` never sees them.
3. Add a shared `is_valid_token()` full-match validator used by sampler, GT export, and documented for stemgen — never rely on `findall` alone for vocabulary membership.
4. Regression tests using the table above as fixtures (audit §5 Phase A explicitly requires this).

**Warning signs:**
- Single-letter tokens (`B`, `H`, `F`, `d`) in vocabulary with TF ≥ 1.
- Vocabulary entries that are strict substrings of known foreign names (`ziera`, `dinger`, `bner`, `caf`).
- `foreign_fragment_rate` audit stat > 0 in `build_summary.json`.
- Common Polish words (`na`, `on`) with TF spikes traceable to foreign sources (WikiNeural worst: `é×43, è×16, ö×14…`).

**Phase to address:**
Cleaning stage (Phase A) + tokenizer alignment (Phase B). Must be verified by full-tier rebuild, not unit tests alone.

---

### Pitfall 2: OOV self-lemma identity rows teaching stemmer garbage

**What goes wrong:**
`builder.py:209` falls back to `morfeusz.dominant_lemma.get(word, word)` — every out-of-vocabulary token (foreign fragment, proper noun, typo, digit truncation) becomes a `(word, word)` identity ground-truth row. Stemgen then learns "stem of `ziera` is `ziera`", i.e. identity mappings for noise. The audit ranks this **high** severity.

**Why it happens:**
Silent fallback defaults feel safe (`get(word, word)` never throws) but they convert an *absence of knowledge* into a *false positive claim*. The proper-noun filter exists in the dictionary path (`morfeusz_extractor.py:91`, `lemma[0].isupper()` before lowercasing) but **not** in the corpus-text path — so proper nouns are filtered from the dictionary yet re-enter through the text and get identity rows anyway (asymmetric filtering, see Pitfall 7).

**How to avoid:**
Per PROJECT.md decision: **drop OOV rows** (no `(word, word)` identity GT). Alternative if traceability is needed: emit with `lemma=NULL` + `oov_flag` so stemgen can exclude them — but never a silent self-lemma. Add `oov_self_lemma_rate` to `build_summary.json` and assert it is 0 (or equals the flagged rate) after rebuild.

**Warning signs:**
- GT rows where `word == lemma` for tokens that are clearly not Polish dictionary words.
- Identity-row rate correlating with WikiNeural genre share.
- Stemmer evaluation showing correct "stemming" of foreign fragments (it memorized noise).

**Phase to address:**
GT hygiene (Phase C).

---

### Pitfall 3: Over-aggressive filtering drops valid Polish (the overcorrection trap)

**What goes wrong:**
The fix for contamination overshoots and deletes legitimate Polish content. Three concrete sub-cases:

**(a) Sentence-level drops kill valid Polish context.** WikiNeural sentences routinely embed a foreign name inside otherwise clean Polish: *"Pierre Bézier był francuskim inżynierem…"*. A sentence-level "drop sentences containing `[^Polish]` diacritics" policy deletes the whole Polish sentence, biasing the corpus against encyclopedic/biographical prose — exactly the genre (Wikipedia) that most needs coverage. Token-level exclusion (drop the foreign *token* from TF/DF, keep the sentence) preserves the Polish context.

**(b) Hyphenated compounds like `biało-czerwony` get mangled.** `VALID_WORD_RE` allows only a *single* internal hyphen (` Saint-Étienne-la-Geneste` → `tienne-la` kept, rest split). Valid Polish compounds (`biało-czerwony`, `polsko-francuski`, `marszrutka-like` formations) survive one hyphen but multi-hyphen foreign chains and Polish double compounds (`biało-czerwono-niebieski`, rare but legal) break. Worse: if cleaning naively strips *all* hyphenated tokens containing a foreign fragment, legitimate Polish hyphen-compounds adjacent to foreign text get caught. Rule: validate each hyphen-separated segment independently; drop/keep per segment, and allow N hyphens for Polish-side validation.

**(c) Blanket lowercase-proper-noun heuristics nuke sentence-initial words.** A tempting shortcut — "drop all capitalized OOV tokens as proper nouns" — deletes every sentence-initial common noun that Morfeusz happens to miss (archaic forms in Wolne Lektury 19th-c. novels like *Lalka*, dialect, typos). Capitalization is a signal, not a verdict: combine with dictionary lookup (OOV + capitalized + not sentence-initial → likely proper noun) rather than case alone.

**Why it happens:**
Strict Polish-only is a *token-validity* decision, but developers implement it at the *sentence/document* granularity because it's fewer lines of code. And proper-noun filtering is easy to write as a case check but hard to write correctly without position + dictionary context.

**How to avoid:**
- Enforce strictness at the **token** level (drop foreign tokens from TF/DF), keep the default at **sentence** level as *retain-with-flagging* unless the sentence is majority-foreign (threshold, e.g. >50% foreign tokens → drop sentence; else drop tokens). Record both rates.
- Hyphen rule: split on hyphens/dashes first, validate segments independently against the Polish alphabet; rejoin only if all segments valid.
- Proper-noun rule: `capitalized AND OOV AND not-sentence-initial` → flag/drop; never case-alone.
- Acceptance fixtures must include positive cases: `biało-czerwony` survives; *"Pierre Bézier był inżynierem"* retains all Polish tokens with only `Bézier` excluded; sentence-initial OOV common nouns are flagged, not silently dropped.

**Warning signs:**
- Token counts drop disproportionately in Wikipedia genre after cleaning (over-drop, not decontamination).
- Valid compounds missing from vocabulary post-rebuild.
- Cleaning removes more Polish sentences than foreign tokens (track both counters separately).

**Phase to address:**
Cleaning stage (Phase A) — acceptance criteria must include *retention* fixtures, not just removal fixtures.

---

### Pitfall 4: Dash/quote normalization ordering and the multi-dash zoo

**What goes wrong:**
Polish text uses `—` (em dash, dialogue!), `–` (en dash, ranges), `-` (hyphen, compounds), plus quotes `„ " « »`. `TOKEN_RE` allows only ASCII `-` with a single internal occurrence. Un-normalized `—`/`–` act as split points exactly like foreign diacritics: *"poszedł — powiedział"* tokenizes fine only because spaces surround the dash, but *"rok 1939–1945"* or *"słowo—drugie"* (no spaces, common in news/Wolne Lektury) fuse or split tokens. Meanwhile `„ ” « »` are harmless only if the tokenizer ignores them — which `findall` does — but stemgen-side tokenizers may not, so stored text and stemgen's view diverge (Pitfall 9's cousin).

19th-c. literature (*Lalka* and others in Wolne Lektury) is dialogue-heavy: em-dash dialogue markers on nearly every line. Mishandling dashes there corrupts the single largest clean-Polish genre.

**Why it happens:**
The existing punctuation fix covers only `[,.:;?!]` and `[("«]` (`text_sources.py:40-41,149-150`). Dashes and closing quotes were never in scope, and dash normalization looks trivial until you realize `-` vs `–` vs `—` carry different semantics (compound vs range vs dialogue break).

**How to avoid:**
Audit §5 Phase A order: NFC → strip `�`/controls → foreign-letter policy → **normalize quotes/dashes** (`„ ” → "`, `— – → -`, with dialogue-dash-at-line-start optionally spaced) → collapse whitespace. Normalize dashes to ASCII `-` *before* token validation so hyphen rules apply uniformly; keep a pre-normalization copy only if dialogue-structure research needs it (out of scope — don't). Fixtures: `"rok 1939–1945"` → `1939-1945` then digit-policy handling; `"— Powiedział —"` dialogue lines survive as Polish tokens.

**Warning signs:**
- Tokens containing `—`/`–` remnants in vocabulary; fused tokens like `słowo—drugie` as single entries.
- Literature-genre token counts shifting anomalously after cleaning.

**Phase to address:**
Cleaning stage (Phase A).

---

### Pitfall 5: Digit/alphanumeric policy edge cases

**What goes wrong:**
`TOKEN_RE` drops digits silently, producing three distinct corruptions visible in the audit:
- `COVID-19 → COVID` (truncation — `COVID` looks like a valid word, pollutes GT the same way `caf` does).
- `model3 → model` (alphanumeric fusion — the count for `model` now includes `model3` occurrences).
- Pure numerics (`2012, 1990, 2016, ²`, present in 20/21 test-build docs) either vanish silently or, if a future regex admits digits, flood vocabulary with years.

The trap: fixing this with "allow digits in tokens" is worse — years and identifiers explode vocabulary and DF statistics become meaningless for stemming (every year appears in few docs → IDF distortion).

**Why it happens:**
No explicit numeric-token policy exists; digits fall through whatever the letter-regex does by accident. Each "obvious" one-line fix (allow digits / strip digits / ignore) fixes one sub-case and worsens another.

**How to avoid:**
Per PROJECT.md decision: **drop pure-numeric and alphanumeric tokens from TF/DF**; record `digit_token_rate` in `build_summary.json`. Explicitly: `2012` → dropped; `COVID-19` → dropped whole (not truncated to `COVID` — truncation is the bug); `model3` → dropped whole. Rationale to encode in code comments: years/identifiers carry no stemmable morphology, and partial retention reintroduces Pitfall 1. Fixture table: `COVID-19`, `model3`, `2012`, `²` all absent from post-clean vocabulary *and* their fragments (`COVID`, `model`) gain zero counts from them.

**Warning signs:**
- `COVID` or year-adjacent tokens with TF inconsistent with clean-text occurrences.
- `digit_token_rate` nonzero post-clean (policy not applied on both paths — see Pitfall 9).

**Phase to address:**
Tokenizer alignment (Phase B) + cleaning (Phase A); verified via audit stat.

---

### Pitfall 6: NFC vs NFD — normalize BEFORE any regex

**What goes wrong:**
Polish diacritics exist in two Unicode forms: composed NFC (`ą` = U+0105, one codepoint) and decomposed NFD (`a` + U+0328 combining ogonek, two codepoints). The allowlist regex `[ąćęłńóśźż…]` matches **only NFC**. NFD text — which appears when sources concatenate strings from macOS filesystems, web forms, or multi-stage pipelines — fails every character class: `biały` in NFD tokenizes as `bia` + `y`-ish fragments with stray combining marks, i.e. Pitfall 1 with valid Polish input. Cleaning that "drops tokens with non-Polish characters" then deletes *correct Polish words* because the combining mark looks foreign.

The audit's NFC check (84k WikiNeural tokens → 0 non-NFC) is a **small-sample negative**: the current 21-doc seed build is not representative, and `errors="replace"` ingestion plus HTML-unescaping (Phase D) can introduce decomposed sequences at full-corpus scale.

**Why it happens:**
`"ą" == "ą"` is True in only one normalization form; developers test with NFC literals (all keyboard input is NFC) and the NFD path never appears in unit tests. The bug surfaces only at corpus scale with heterogeneous sources.

**How to avoid:**
`unicodedata.normalize("NFC", text)` as the **first** operation in `clean_text()`, before stripping, validation, or regex — order is load-bearing. Add explicit NFD fixtures: `unicodedata.normalize("NFD", "biało-czerwony ącki")` must clean to the identical result as the NFC input. Never use NFD internally (macOS-filesystem arguments don't apply to corpus text processing).

**Warning signs:**
- Combining-mark codepoints (U+0300–U+036F) in stored docs or vocabulary.
- Valid Polish words missing from vocabulary with no other explanation; token counts differing between NFC/NFD fixture runs.

**Phase to address:**
Cleaning stage (Phase A) — first line of `clean_text()`; NFD fixtures in regression tests.

---

### Pitfall 7: Proper-noun asymmetry between dictionary and corpus paths

**What goes wrong:**
Two sub-failures in opposite directions:
- **Under-filtering (current bug):** dictionary drops proper nouns (`morfeusz_extractor.py:91`) but corpus text keeps them → OOV identity rows (Pitfall 2). Foreign names (`Schrödinger`, `Saint-Étienne-la-Geneste`) flow straight through.
- **Over-filtering (likely overcorrection):** "fixing" this by dropping all capitalized words from corpus text destroys sentence-initial tokens and legitimate capitalized common nouns (titles, *Lalka*-era capitalization conventions, `Polak`/`polski` adjective/noun distinctions that Morfeusz resolves via case).

**Why it happens:**
The dictionary and the corpus are filtered by different code with different rules (`VALID_WORD_RE` *rejects* foreign forms while `TOKEN_RE` *splits* them — audit issue #4). Any fix applied to only one side preserves the divergence.

**How to avoid:**
Single shared `is_valid_token()` + shared proper-noun heuristic used by sampler, GT export, and documented for stemgen (audit Phase B). Rule shape: dictionary-membership first (in Morfeusz dict → keep regardless of case), then `capitalized + OOV + not-sentence-initial → drop/flag`. Sentence position must be computed on the *cleaned* text, not raw (quotes/dashes shift "first token" — interacts with Pitfall 4).

**Warning signs:**
- GT identity rows dominated by capitalized tokens (under-filtering persists).
- Post-fix vocabulary missing common sentence-initial words vs. pre-fix baseline (over-filtering).

**Phase to address:**
Tokenizer alignment (Phase B) + GT hygiene (Phase C).

---

### Pitfall 8: Re-pass duplication skewing DF

**What goes wrong:**
All four `iter_*_docs` generators (`text_sources.py:56-66, 90-100, 122-132, 154-164`) use `while count < max_docs:` loops that **re-create the source generator and re-chunk from the start** when the source is smaller than requested. Re-yielded documents are byte-identical duplicates. TF merely inflates (bad), but **DF is structurally corrupted**: the same document counted N times makes its terms look document-frequent, crushing their IDF weight and distorting any DF-sensitive stemmer training signal. Duplicates are also adjacent-in-time, so spot-checking "a few docs" rarely catches them.

**Why it happens:**
The loop was written for "keep yielding until quota" convenience during small test builds (21-doc seed build). At full-tier scale with genre quotas exceeding small sources (e.g. literature subset), it silently duplicates instead of failing. No content-hash `seen` set, no warning log.

**How to avoid:**
Per audit Phase D: content-hash `seen` set (e.g. `hashlib.sha256(doc.encode())`) in each `iter_*_docs`; on repeat, either stop iteration (fail/return with logged warning) or skip-and-continue — **never re-yield**. Add a `duplicate_doc_rate` counter to build stats; assert 0 after full-tier rebuild. Note the interaction: cleaning *before* hashing vs after changes hash identity — hash the final stored text so the guard matches what's archived.

**Warning signs:**
- `doc_freq` values with suspiciously round multiples; identical TF vectors across doc IDs.
- Genre doc counts exactly hitting quota on sources known to be small.
- DF distribution with spikes at multiples of pass count.

**Phase to address:**
Source hardening (Phase D); DF-sensitive verification after full-tier rebuild.

---

### Pitfall 9: Stored-text / counted-token disagreement (clean on ONE path only)

**What goes wrong:**
`add_document()` (`corpus_sampler.py:73-91`) writes `text` to zip **and** counts `TOKEN_RE.findall(text)` — two consumers of one string. If `clean_text()` is applied to only one path (clean before write but count raw, or vice versa), the archive and TF/DF silently disagree: either the zip contains tokens with zero counts, or counts reference tokens absent from the zip. Downstream, stemgen trains on GT rows that don't match the archived documents — an inconsistency no unit test on either path alone will catch, and a schema-compatible corruption (nothing errors).

This is also the exact shape of the *original* bug (raw write + truncating count), so a half-applied fix reproduces the audit's root cause with new symptoms.

**Why it happens:**
Two lines consuming the same variable look like one operation; a developer inserts cleaning into the write line and considers counting "already handled", or cleans a local copy for counting without storing it.

**How to avoid:**
Clean once at the top of `add_document()`: `text = clean_text(text)` then use `text` for **both** `writestr` and `findall`. Structural prevention beats discipline: make the raw string unnameable after cleaning (reassign, don't branch). Verification: rebuild-time assertion sampling docs from the zip, re-tokenizing with the shared tokenizer, and comparing against recorded TF/DF (the "stored and counted agree" invariant from PROJECT.md constraints). This check belongs in the full-tier rebuild verification, not just unit tests.

**Warning signs:**
- Spot-check mismatches between zip doc text and GT TF for the same term.
- `foreign_fragment_rate == 0` in GT but foreign characters present in zip docs (cleaned counts, raw write) or vice versa.

**Phase to address:**
Cleaning stage (Phase A); invariant check in final rebuild verification.

---

### Pitfall 10: Two tokenizers that diverge by design (sampler vs dictionary)

**What goes wrong:**
`TOKEN_RE` (sampler, extraction semantics: splits) and `VALID_WORD_RE` (extractor, validation semantics: rejects) encode *different policies in different shapes*. Even after cleaning, edge inputs behave differently per path: multi-hyphen names, leading/trailing hyphens, single letters, digit-adjacent tokens. The vocabularies then diverge: GT export sees words the dictionary never validated and vice versa, and stemgen's own third tokenizer adds a further undocumented divergence (audit issue #3 notes raw text and `TOKEN_RE` counts can already disagree with stemgen's tokenizer).

**Why it happens:**
Each regex was written for its local call site with no shared contract. `^[…]+(-[…]+)?$` (validate) vs `[…]+(?:-[…]+)?` (extract) *look* equivalent but differ on exactly the adversarial inputs (multiple hyphens, boundary hyphens, empty segments).

**How to avoid:**
One canonical module (e.g. shared tokenizer/validator next to `clean_text()`): `TOKEN_RE` for extraction + `is_valid_token()` for membership, imported by `corpus_sampler`, `morfeusz_extractor`, GT export, and **published/documented for the stemgen side** (PROJECT.md requirement: "single shared tokenizer/validator … documented for stemgen"). Differential test: every token produced by extraction over the audit fixture table must yield the same keep/drop verdict as direct validation — no input where extract-says-yes and validate-says-no.

**Warning signs:**
- GT words failing `VALID_WORD_RE`; dictionary words unproducible by `TOKEN_RE`.
- Bug reports of the form "fixed in sampler, still broken in GT".

**Phase to address:**
Tokenizer alignment (Phase B); contract test in regression suite.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| `errors="replace"` on all ingestion (`text_sources.py:27,77,111,141`) without counting `�` | Never crashes on bad bytes | Silent `�` injection into docs; currently unmeasured (audit found none in 21-doc sample — unrepresentative) | Only with a `replacement_char_rate` counter + strip in `clean_text()`; never bare |
| Weak Wolne Lektury boilerplate filter (3 substrings + `len > 20`) | 3 lines, works on current sample | Headers/footers, `Rozdział` markers, page numbers leak at full-literature scale | Never as final; Phase D must add header/footer, chapter-marker, page-number patterns |
| Assuming `row[1]` is clean in news CSV path (no HTML-unescape/URL strip) | Works on current clean sample | Markup/entities/URLs enter corpus the moment the source adds a feed with HTML | Never as final; Phase D unescape + strip |
| Punctuation fix covering only `[,.:;?!]` + `[("«]` | Fixes observed spacing | Dashes/closing quotes diverge (Pitfall 4); stemgen-side mismatch | Only until Phase A normalization lands |
| `(word, word)` OOV fallback | GT export never drops rows; counts look complete | Trains identity mappings for noise (Pitfall 2) | Never — drop or `lemma=NULL` + flag |
| `while count < max_docs` re-pass loops | Quotas always fill in test builds | Duplicate docs, skewed DF (Pitfall 8) | Never — `seen`-hash guard or fail loudly |
| Per-call-site regexes (`TOKEN_RE` vs `VALID_WORD_RE`) | No coupling, fast to write | Policy divergence (Pitfall 10) | Never — shared module from Phase B onward |
| 21-doc seed build as verification | Fast iteration | Proves nothing about full-tier contamination (WikiNeural tail, *Lalka* French dialogues surface only at scale) | Only for smoke tests; zero-fragment claim requires full-tier rebuild |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| Morfeusz/PoliMorf dictionary build | Reusing `VALID_WORD_RE` for corpus text (reject-semantics where split-semantics operate) | Shared `is_valid_token()`; dictionary path and corpus path import the same validator |
| Morfeusz homonym qualifiers (`piec:s1`) | Cleaning `clean_lemma` output with word-regexes that choke on `:` | Strip qualifiers (`clean_lemma`) *before* validation — already done in extractor; preserve this order in any refactor |
| stemgen consumer tokenizer | Assuming stemgen tokenizes like this pipeline; shipping GT without tokenizer docs | Publish the shared tokenizer/validator spec with the corpus release (PROJECT.md requirement); GT rows must be reproducible from archived docs using the published spec |
| `ground_truth.parquet` schema (`word, lemma, tf, df`) | Adding `oov_flag`/`lemma=NULL` without versioning breaks stemgen parsers | PROJECT.md constraint: schema stays compatible unless explicitly versioned — coordinate nullable-lemma or drop-rows decision with stemgen owner before changing shape |
| WikiNeural `tokens` field | Assuming pre-tokenized source tokens are clean (they contain `Béziera`, `Saint-Étienne-la-Geneste` verbatim) | Treat source tokens as *raw text fragments*, rejoin + `clean_text()`; never trust upstream tokenization |
| News CSV `row[1]` | Assuming article-text column position/format stable across `news_articles.csv` / `news_test.csv` | Validate column by header name where possible; HTML-unescape + markup strip regardless |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Cleaning loads full corpus into memory | OOM on full-tier build; works on 21-doc test build | PROJECT.md constraint: cleaning must stream (generator-per-doc, constant memory); never `read()` whole zip/source | Full-tier builds (all three tiers) |
| Per-token `unicodedata.normalize` inside hot loop instead of per-document | 10–100× slowdown on full builds | Normalize once per document string at `clean_text()` entry, not per token | Full-tier rebuild time budget |
| `seen`-hash set growing unbounded (Pitfall 8 guard) | Memory creep on largest tier | Store 64-bit truncated digests (`sha256(d).digest()[:8]`) — collision risk negligible vs. memory win at this scale; or per-genre sets released after genre completes | Extended tier, if ever an issue — measure first |
| Full-vocabulary differential test on every commit | CI minutes balloon as vocab grows | Differential extract-vs-validate test runs on the *fixture table* (≈20 strings), not the corpus; corpus-scale agreement check runs only in rebuild verification | As vocabulary passes ~100k entries |

## "Looks Done But Isn't" Checklist

- [ ] **Cleaning:** `foreign_fragment_rate == 0` in GT — but did you check the *zip docs* too? (Pitfall 9: one clean path ≠ both.) Verify fragments absent from docs **and** counts.
- [ ] **Cleaning:** Fixture tests pass — but do they include *retention* positives (`biało-czerwony`, Polish sentence with `Bézier`, NFD input)? Removal-only fixtures hide over-filtering (Pitfall 3).
- [ ] **Digit policy:** `COVID-19` absent — but did `COVID` gain phantom counts? Check the *fragment*, not just the whole token (Pitfall 5).
- [ ] **OOV hygiene:** No `(word, word)` rows — or did the fallback move (e.g. into `snowball_voc_ground_truth` or the 80/20 split code)? Grep all GT-producing paths, including `build_snowball_voc_ground_truth` and `create_lemma_stratified_split` inputs (Pitfall 2).
- [ ] **Dedup:** Quotas filled exactly — with *unique* docs? Check `duplicate_doc_rate == 0` and DF sanity, not just doc counts (Pitfall 8).
- [ ] **NFC:** Unit tests pass with literal `"ącki"` — NFC by construction. Did you test explicit NFD input? (Pitfall 6.)
- [ ] **Tokenizer unity:** Sampler and extractor agree on fixtures — and is stemgen's side documented/pinned, or will its tokenizer silently diverge next release? (Pitfall 10.)
- [ ] **Scale:** Green on the 21-doc seed build — meaningless for contamination claims. Zero-fragment verdict requires the **full-tier rebuild** with audit stats (PROJECT.md validation criterion).
- [ ] **Proper nouns:** Identity rows gone — but did sentence-initial common nouns vanish from vocabulary too? Diff pre/post vocabulary for asymmetric loss (Pitfall 7).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Split-not-drop fragments already in GT | MEDIUM | No data loss (raw sources intact): fix cleaning + shared validator, drop OOV rows, full rebuild; old GT artifacts discarded, schema unchanged |
| OOV identity rows shipped to stemgen | HIGH | Corpus-side: rebuild clean GT. Stemgen-side: retrain (identity mappings are baked into model weights — cannot be patched by corpus fix alone); coordinate versioned re-release |
| Over-aggressive filtering deleted valid Polish | LOW–MEDIUM | Loosen to token-level policy, add retention fixtures, rebuild; lost content was never destroyed (sources re-readable) — cost is rebuild time only |
| Re-pass duplicates skewed published DF | MEDIUM | Add `seen` guard, rebuild; any stemmer trained on skewed DF needs retraining evaluation (measure IDF-sensitive metrics before deciding) |
| Stored/counted disagreement shipped | HIGH | Both artifacts suspect: rebuild with single-clean-point + agreement assertion; invalidate prior `corpus.zip` + GT pairs as a unit (never mix old zip with new GT) |
| NFD corruption in archived docs | LOW | Rebuild with NFC-first cleaning; archived docs are regenerable from sources |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| 1 Split-not-drop tokenization | Phase A (cleaning) + B (shared validator) | Fixture table (Béziera…Linköping) → zero fragments; `foreign_fragment_rate == 0` after full-tier rebuild |
| 2 OOV identity rows | Phase C (GT hygiene) | `oov_self_lemma_rate == 0` (or all flagged); grep all GT paths for fallback |
| 3 Over-aggressive filtering | Phase A (acceptance criteria) | Retention fixtures (`biało-czerwony`, Bézier-sentence, NFD pair) green; per-genre token deltas reviewed |
| 4 Dash/quote normalization | Phase A (normalization step) | Dialogue/range fixtures; literature-genre spot checks |
| 5 Digit policy | Phase A + B | `COVID-19/model3/2012/²` fixtures; `digit_token_rate` recorded; fragment-count check |
| 6 NFC vs NFD | Phase A (`clean_text()` line 1) | Explicit NFD fixtures byte-identical to NFC results |
| 7 Proper-noun asymmetry | Phase B + C | Shared validator import test; pre/post vocab diff for asymmetric loss |
| 8 Re-pass duplication | Phase D (dedup guard) | `duplicate_doc_rate == 0`; DF distribution sanity after rebuild |
| 9 Stored/counted disagreement | Phase A (single clean point) | Zip-sample re-tokenize vs recorded TF/DF agreement assertion in rebuild verification |
| 10 Tokenizer divergence | Phase B (shared module) | Differential extract-vs-validate test on fixture table; stemgen-side spec published |

## Sources

- `quality-audit.md` (2026-10-16, repo root) — primary evidence: verified `TOKEN_RE` truncation table (§2), per-source foreign-letter frequencies (§3), ranked issues + remediation Phases A–D (§4–5). HIGH confidence.
- `src/polish_corpus/corpus_sampler.py:20,73-91` — `TOKEN_RE` definition; raw-write + truncating-count in `add_document`. HIGH confidence (direct read).
- `src/polish_corpus/text_sources.py` — `errors="replace"` ingestion, narrow punctuation fix, weak Wolne Lektury filter, `while count < max_docs` re-pass loops in all four `iter_*_docs`. HIGH confidence (direct read).
- `src/polish_corpus/morfeusz_extractor.py:23,91` — `VALID_WORD_RE` vs `TOKEN_RE` divergence; proper-noun filter on dictionary path only. HIGH confidence (direct read).
- `src/polish_corpus/builder.py:209-211` — OOV `(word, word)` fallback; GT/split/snowball export paths. HIGH confidence (direct read).
- Unicode Standard normalization (NFC vs NFD, combining marks U+0300–U+036F) — general standard knowledge applied to the PolishAlphabet regex interaction; NFD fixtures recommended as hardening beyond the audit's small-sample NFC check. MEDIUM-HIGH confidence (mechanism certain, full-scale NFD prevalence unmeasured — flagged as open measurement, not fact).

---
*Pitfalls research for: Corpus Quality Hardening for stemgen-polish-corpus*
*Researched: 2026-10-16*
