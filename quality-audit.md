# Corpus Quality Audit — Foreign Diacritics & Data Issues

Date: 2026-10-16
Scope: `stemgen-polish-corpus` text pipeline (corpus docs + ground-truth export feeding stemgen stemmer training).
Trigger: strange (non-Polish) diacritics in some documents cause noise in the generated stemmer.

## 1. Verdict

Yes — refine the text cleaning logic. There is currently **no cleaning/normalization stage**
between raw source ingestion (`src/polish_corpus/text_sources.py`) and archive output
(`src/polish_corpus/corpus_sampler.py:73-91`). Foreign words are written verbatim into
`corpus.zip` while the TF/DF counter silently **truncates** them into garbage fragments,
which then leak into `ground_truth.parquet` as self-lemma rows and into stemgen training.

## 2. Root cause

- `TOKEN_RE` (`src/polish_corpus/corpus_sampler.py:20`) and `VALID_WORD_RE`
  (`src/polish_corpus/morfeusz_extractor.py:23`) accept only
  `[a-zA-Z]` + Polish `ąćęłńóśźż` (+ single internal hyphen).
- `BalancedCorpusWriter.add_document()` (`src/polish_corpus/corpus_sampler.py:73-91`)
  does `self.zip_file.writestr(filename, text)` on the **raw** text, but computes
  `tokens = TOKEN_RE.findall(text)` for TF/DF. A foreign letter acts as a split point.
- Ground-truth export (`src/polish_corpus/builder.py:209-211`) falls back to
  `morfeusz.dominant_lemma.get(word, word)`, so every truncated fragment becomes a
  `(word, word)` identity row that stemgen learns.

Observed truncation behavior (verified against current `TOKEN_RE`):

| Input | Tokens produced | Problem |
|---|---|---|
| `Béziera` | `B`, `ziera` | 2 garbage rows |
| `Besançon` | `Besan`, `on` | fragment + stopword-like `on` |
| `Turčianske` | `Tur`, `ianske` | fragments |
| `Saint-Étienne-la-Geneste` | `Saint`, `tienne-la`, `Geneste` | partial hyphen handling |
| `Corrèze` | `Corr`, `ze` | fragment |
| `Schrödinger` | `Schr`, `dinger` | fragments |
| `Hübner` | `H`, `bner` | single-letter `H` + fragment |
| `Maréchal` | `Mar`, `chal` | fragments |
| `désintéressement` | `d`, `sint`, `ressement` | fragments |
| `Führer` | `F`, `hrer` | fragments |
| `café` | `caf` | truncated stem |
| `naïve` | `na`, `ve` | fragments |
| `COVID-19` | `COVID` | digit part silently dropped |
| `Linköping` | `Link`, `ping` | fragments |

## 3. Evidence by source (3k-sample scans of `data_cache/`)

- **`04_wikipedia` (WikiNeural) — worst offender.** Foreign-letter freq: `é×43, è×16,
  ö×14, á×12, ü×11, ô×8, í×8, Î×8, É×6, ø×6, ã×6, č×4, ñ×4, â×4, å×4, š×4, ç×3,
  ä×3, ...` plus Cyrillic `е/о/р/д/и/в` and `ș/ß/ê/ō/ā/ú`.
  Examples: `Béziera, Besançon, Turčianske Teplice, Anthé, Saint-Étienne-la-Geneste,
  Corrèze, Antônio Pizzonia, Schrödinger`.
- **`01_nkjp_spoken_forum` / `03_nkjp_news` (NKJP1M + news CSV).**
  NKJP: `é×4, ü×2` — `Maréchal Niel, Éveline, désintéressement, Mein Führer,
  la plus aimée de reines, Hübner`.
  News: `ü×6, é×2, ä×1` — `Freie Universität Berlin, Flügla, Hübner, Desiré Kabila`.
- **`02_nkjp_literature` (Wolne Lektury) — mostly clean** (`ö×1`: `Linköping`),
  but 19th-c. novels (e.g. `Lalka`) contain French dialogues/quotations that will
  surface at full-corpus scale.
- **Encoding:** NFC check on 84k WikiNeural tokens → 0 non-NFC. `errors="replace"`
  (`text_sources.py:27,77,111,141`) can inject `�`, but none found in the current
  small `output/general/corpus.zip` (21 docs, seed-dominated test build).

## 4. Other data issues found (ranked)

1. **OOV self-lemma pollution (high).** Proper nouns are filtered from the
   *dictionary* (`morfeusz_extractor.py:91`, `lemma[0].isupper()` check before
   lowercasing) but **not** from *corpus text*. Every OOV token — proper noun,
   foreign fragment, typo — becomes `(word, word)` via `builder.py:209-211`.
   Trains stemgen toward identity mappings for noise.
2. **Digit/alphanumeric truncation (medium).** `TOKEN_RE` drops digits:
   `COVID-19→COVID`, `model3→model`. Digit tokens are common in sources
   (`2012, 1990, 2016, ², 1997, ...`); 20/21 docs in the test `corpus.zip`
   contain digit tokens. No explicit numeric-token policy exists.
3. **No normalization stage (medium).** No NFC enforcement, no `�`/control-char
   stripping, no `„ ” « » — –` normalization. Punctuation spacing fix only covers
   `[,.:;?!]` and `[("«]` (`text_sources.py:40-41,149-150`). Raw doc text and
   `TOKEN_RE` counts can disagree with stemgen's own tokenizer.
4. **Dictionary/corpus tokenizer mismatch (medium).** `VALID_WORD_RE` *rejects*
   foreign forms outright (good) while `TOKEN_RE` *splits* them (bad) — the two
   vocabularies diverge by design. Fix requires one shared validator.
5. **Weak literature boilerplate filtering (low-medium).** Only skips lines with
   `Ten utwór... / ISBN / Wolne Lektury` + `len(line) > 20`
   (`text_sources.py:79-84`). Headers/footers, `Rozdział` markers, page numbers can leak.
6. **Re-pass duplication risk (low-medium).** `iter_*_docs` `while count < max_docs`
   loops (`text_sources.py:56-66,90-100,122-132,154-164`) re-create the source
   generator and re-chunk when the source is small → duplicate docs, skewed DF.
   Add seen-hash guard or fail instead of re-yielding.
7. **Unguarded HTML/entity/URL path (low).** News CSV path
   (`text_sources.py:109-116`) assumes `row[1]` is clean article text; no
   HTML-unescape, markup, or URL stripping. Clean in current sample, but unguarded.

## 5. Remediation plan

### Phase A — Text cleaning (core fix)
- Add `clean_text()` (new `text_cleaning.py`, or in `corpus_sampler.py`):
  NFC → strip `�` / control chars → foreign-letter policy (see §6) →
  normalize quotes/dashes (`„ ” → "`, `— – → -`) → collapse whitespace.
- Apply **before** `writestr` **and** before `TOKEN_RE` counting so stored docs and
  TF/DF agree.
- Add unit tests with the table in §2 as fixtures.

### Phase B — Tokenizer alignment
- Single shared `TOKEN_RE` + `is_valid_token()` used by sampler, GT export, and
  documented for the stemgen side.
- Explicit digit policy (recommended: drop pure-numeric tokens and strip/flag
  alphanumeric tokens from TF/DF; record counts in `build_summary.json`).

### Phase C — Ground-truth hygiene
- Stop emitting silent `(word, word)` identity rows for OOV. Options: drop them,
  or emit with `lemma=NULL` + `oov_flag` so stemgen can exclude them.
- Filter or flag proper-noun-like OOV and foreign-fragment tokens at export.
- Add audit stats to `build_summary.json`: `oov_self_lemma_rate`,
  `foreign_fragment_rate`, `digit_token_rate`.

### Phase D — Source hardening (cheap, opportunistic)
- Stronger Wolne Lektury boilerplate patterns; HTML-unescape for news/wiki;
  URL/e-mail handling; dedup guard (content-hash `seen` set) in `iter_*_docs`.

## 6. Open decisions (need owner input)

1. **Foreign-text policy:** strict Polish-only (drop tokens/sentences containing
   `[^Polish]` diacritics) vs. lenient (keep sentence, exclude foreign token from
   TF/DF, optionally keep surface form in raw doc but flagged)?
2. **OOV ground truth:** keep `(word, word)` self-lemma rows, drop them, or flag
   with `lemma=NULL`? This changes stemgen training data shape.
3. **Scope:** Phase A+B only, or A–D in one change?

## 7. Reproduction notes

- Scans run with repo `.venv` Python against `data_cache/nkjp1m_train.jsonl.gz`,
  `data_cache/literature/*.txt`, `data_cache/news_articles.csv`,
  `data_cache/news_test.csv`, `data_cache/wiki_pl.jsonl`.
- Truncation table verified with
  `TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)?")`.
- `output/general/` in the working tree is a 21-doc seed-dominated test build
  (`build_summary.json`: 5,768 tokens, 336 vocab), not a full tier build —
  re-run audit stats after the next full build.
