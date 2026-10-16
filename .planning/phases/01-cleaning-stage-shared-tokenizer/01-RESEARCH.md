# Phase 1: Cleaning Stage + Shared Tokenizer — Research

**Researched:** 2026-10-16 · **Domain:** stdlib text cleaning + tokenizer alignment · **Confidence:** HIGH

Locked: token-level DROP (foreign + alphanumeric), stdlib only, choke point at writer gate, no GT-export or cross-repo changes. Builds on project SUMMARY.md — no stack/alternatives re-analysis.

## 1. Exact insertion points

- **NEW `src/polish_corpus/text_cleaning.py`** — sole owner of `TOKEN_RE`, `is_valid_token()`, `clean_text()`, `tokenize()`. Pure functions, no I/O. `TOKEN_RE` moves here verbatim from `corpus_sampler.py:20`, then sampler/extractor import it (delete local copies).
- **Writer gate — `corpus_sampler.py:73` (`add_document`, first line):** `text = clean_text(text)` before `writestr(:91)` AND before `TOKEN_RE.findall(:83)`. Stored docs and TF/DF agree by construction. No other call site needed for correctness.
- **Counting alignment — `corpus_sampler.py:23-25` (`count_words`) and `:83`:** both switch to shared `tokenize()` = `[t for t in TOKEN_RE.findall(cleaned) if is_valid_token(t)]`. `chunk_text_stream(:28-54)` uses shared `count_words` unchanged in shape.
- **Out of scope for this phase:** `add_paradigm_batch(:109-126)` (forms already clean, counted directly — do NOT gate), `builder.py` GT loop, `morfeusz_extractor.py` (import swap only if trivial).

## 2. Load-bearing ordering inside `clean_text()`

`unicodedata.normalize("NFC", s)` → strip `�` + control chars (`unicodedata.category(ch).startswith("C")`, keep `\n\t`) → `html.unescape(s)` → token-level foreign/numeric DROP (regex-split on whitespace, drop any token matching `[^a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ-]` remainder incl. digits/Cyrillic — whole token, no salvage) → quote/dash normalize (`„ " " « » → "`, `— – → -`) → whitespace collapse. NFC first (NFD combining marks evade the class test); unescape before filter (`&eacute;`→`é` must hit the filter); filter before punctuation normalize (don't launder `COVID-19` into countable `COVID`).

`is_valid_token(t)`: `TOKEN_RE.fullmatch(t)` AND no digit AND no char outside Polish class AND each hyphen segment non-empty and Polish-only (`biało-czerwony` passes; `Saint-Étienne` drops whole).

## 3. Edge cases planner must handle

- **Hyphenated compounds retained:** validate each hyphen segment independently; `biało-czerwony` kept, foreign-hyphenated dropped whole (no `tienne-la` salvage).
- **Empty-after-clean paragraphs:** `chunk_text_stream` already skips `para_words == 0 (:42-43)` — cleaned-to-empty paras flow through that path; add test.
- **Word-count agreement:** `chunk_text_stream` counts via shared `count_words` on raw paras while writer counts cleaned docs — sizes may drift slightly; acceptable (sizing only), correctness gate is `add_document`.
- **Paradigm path:** `add_paradigm_batch` counts `forms` list directly, no `findall` — leave untouched.
- **Single letters:** `H` from `Hübner` drops with its token (whole-token drop, never orphan fragments).

## 4. Test fixtures (from quality-audit.md §2)

Drop-cases: `Béziera→∅` (`B`+`ziera` today), `Schrödinger`, `café→∅` (not `caf`), `Besançon`, `Turčianske`, `Corrèze`, `Hübner`, `Maréchal`, `désintéressement`, `Führer`, `naïve`, `Linköping`, `Saint-Étienne-la-Geneste` (whole, no `tienne-la`). Numeric: `COVID-19→∅` (not `COVID`), `2012`, `model3` excluded from TF/DF. Retention: `biało-czerwony`, sentence-initial capitals, `chrząszcz`, `źdźbło`. Ordering: `&eacute;`→dropped post-unescape; NFD `e + ́`→NFC→dropped. Zip-vs-TF/DF agreement test on a dirty sample.
