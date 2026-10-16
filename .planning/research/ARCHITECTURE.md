# Architecture Research: clean_text Placement & Shared Tokenizer

**Domain:** Streaming Polish corpus pipeline (`text_sources.py` → `corpus_sampler.py` → `builder.py`)
**Researched:** 2026-10-16
**Confidence:** HIGH (verified against repo source: `corpus_sampler.py`, `text_sources.py`, `builder.py`, `morfeusz_extractor.py`, `paradigm_generator.py`, `benchmark_splitter.py`, `config.py`)

## Standard Architecture

### System Overview (current, as built)

```
┌──────────────────────────────────────────────────────────────────────┐
│ INGESTION  (`text_sources.py`) — 4 genre generators, NO cleaning      │
│  _stream_nkjp_sentences ─┐                                            │
│  _paragraphs (literature)│─→ join tokens + light punct fix ─→ yield  │
│  _articles (news CSV)    │   (errors="replace" can inject �)          │
│  _sentences (wiki)      ─┘                                            │
├──────────────────────────────────────────────────────────────────────┤
│ CHUNKING  (`corpus_sampler.chunk_text_stream`) — pure assembler       │
│  count_words() via TOKEN_RE on RAW text → ~500-word docs             │
│  iter_*_docs: `while count < max_docs` re-pass loop (dup risk)       │
├──────────────────────────────────────────────────────────────────────┤
│ ARCHIVE-WRITE  (`BalancedCorpusWriter.add_document`) — THE BUG SEAM  │
│  writestr(RAW text)              ← stored docs dirty                  │
│  TOKEN_RE.findall(RAW text)      ← TF/DF fragmented (B+ziera, caf…)  │
├──────────────────────────────────────────────────────────────────────┤
│ GROUND TRUTH  (`builder.py:207-211` + `morfeusz_extractor.py`)       │
│  dominant_lemma.get(word, word)  ← OOV self-lemma identity rows      │
│  VALID_WORD_RE (2nd copy of TOKEN_RE, reject-vs-split mismatch)      │
│  splits + Snowball export + build_summary.json (no audit stats)      │
└──────────────────────────────────────────────────────────────────────┘
```

Three downstream consumers must agree on one vocabulary: **stored `corpus.zip` docs**,
**`term_freq`/`doc_freq` counters**, and **`ground_truth.parquet` rows**. Today all three
derive from raw text through two divergent regexes, so they disagree by construction.

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `text_cleaning.py` (NEW) | Own `TOKEN_RE`, `is_valid_token()`, `clean_text()`, digit policy, audit helpers | Pure functions, module-level compiled regexes, no I/O, no state |
| `text_sources.py` (edit) | Source-specific sanitize (HTML-unescape, boilerplate, URLs) + per-paragraph `clean_text` before chunking | Thin calls at generator yields; content-hash `seen` dedup guard |
| `chunk_text_stream` (reuse, minimal edit) | Assemble paragraphs into ~500-word docs; stays a pure assembler | Switch `count_words` to shared `tokenize`; NO cleaning logic inside |
| `BalancedCorpusWriter.add_document` (edit) | **Enforcement gate:** `clean_text` first, then write + count from cleaned text | 2–3 line change; the correctness invariant lives here |
| `builder.py` GT loop (edit) | Drop OOV / invalid tokens instead of `(word, word)` fallback; emit audit stats | Copy the Snowball pattern (`benchmark_splitter.py` already drops OOV via bare `.get`) |
| `morfeusz_extractor.py` (edit) | Import shared validator; delete local `VALID_WORD_RE` copy | Import-only change |

## Recommended Project Structure

```
src/polish_corpus/
├── text_cleaning.py      # NEW — single owner of TOKEN_RE, clean_text(), is_valid_token(),
│                         #          digit policy, foreign-fragment audit helpers
├── corpus_sampler.py     # EDIT — import shared tokenizer; clean gate in add_document;
│                         #          count_words via shared tokenize; validate paradigm batches
├── text_sources.py       # EDIT — per-paragraph clean_text; HTML-unescape (news/wiki);
│                         #          stronger WL boilerplate; URL handling; seen-hash dedup
├── morfeusz_extractor.py # EDIT — import VALID_WORD_RE/is_valid_token; delete local copy
├── builder.py            # EDIT — GT loop drops OOV + invalid tokens; audit stats to JSON
├── benchmark_splitter.py # REUSE AS-IS — Snowball path already drops OOV; reference pattern
├── paradigm_generator.py # NO CHANGE NEEDED — forms come from filtered dictionary;
│                         #          add_paradigm_batch asserts shared is_valid_token (1 line)
└── config.py             # NO CHANGE
```

### Structure Rationale

- **`text_cleaning.py` (new module, not in-place):** the regex currently lives in two files
  with opposite semantics (`TOKEN_RE` splits foreign text, `VALID_WORD_RE` rejects it).
  A third copy or an in-place fix in one file leaves the divergence intact. One module
  with one `TOKEN_RE`, one `is_valid_token()`, and one `clean_text()` makes
  "stored docs = counted tokens = GT rows" provable instead of aspirational. It is also
  the artifact stemgen is pointed at ("documented for stemgen" requirement).
- **Thin edits elsewhere:** every other seam is a 1–5 line call-site change. This keeps
  the streaming architecture untouched — no new classes, no pipeline re-plumbing, no
  signatures changing for `iter_*_docs` or `chunk_text_stream`.

## Architectural Patterns

### Pattern 1: Writer-boundary enforcement gate (PRIMARY recommendation)

**What:** `clean_text()` runs as the first statement of
`BalancedCorpusWriter.add_document()`, and both `writestr` and `TOKEN_RE.findall`
consume its output. No raw text crosses the writer boundary.

**When to use:** This is the core fix — always.
**Trade-offs:** One choke point covers genre docs, seed-doc fallback (`builder.py:182`),
and any future producer, because all of them funnel through `add_document`. Cost is one
regex pipeline per doc, negligible next to zip compression I/O.

**Example:**
```python
# corpus_sampler.py — the gate (2-line change + import)
from .text_cleaning import clean_text, tokenize

def add_document(self, genre: str, text: str) -> str:
    text = clean_text(text)                       # <-- THE GATE: clean once
    ...
    tokens = [t.lower() for t in tokenize(text)] # counts agree with stored text
    ...
    self.zip_file.writestr(filename, text)        # stored text is the cleaned text
```

### Pattern 2: Idempotent two-layer cleaning (ingestion pre-clean + writer gate)

**What:** Apply the same idempotent `clean_text` at two levels: per-paragraph in
`text_sources.py` generators (before `chunk_text_stream`) AND per-doc in `add_document`.
Idempotence (`clean(clean(x)) == clean(x)`) makes double application safe.

**When to use:** Always — the layers solve different problems:
- Ingestion pre-clean fixes **chunk sizing**: `count_words` currently sizes docs on raw
  text, so dropped foreign tokens would otherwise make docs shorter than the ~500-word
  target (matters most for `Lalka`-style French passages and WikiNeural).
- Writer gate fixes **correctness**: guarantees agreement even for paths that bypass
  ingestion entirely (seed docs, future producers).

**Trade-offs:** Two call sites instead of one, but each is one line, and only the writer
gate is load-bearing for correctness. The ingestion call is a sizing-accuracy
optimization — safe to land in a later phase if needed.

**Example:**
```python
# text_sources.py — per-paragraph pre-clean (one line at each generator's yield point)
from .text_cleaning import clean_text

sentence = clean_text(sentence)  # before yield; chunker then counts clean words
```

### Pattern 3: Validate-at-export for ground truth (drop, don't fall back)

**What:** The GT loop filters through the shared validator and drops OOV rows instead
of emitting `(word, word)` identity rows. This copies the existing Snowball pattern.

**When to use:** `builder.py:207-211` GT export.
**Trade-offs:** Dropping (vs. `lemma=NULL` + flag) is simpler, keeps the
`(word, lemma, tf, df)` schema untouched (compatibility constraint), and matches what
`build_snowball_voc_ground_truth` already does (`benchmark_splitter.py:67-69` uses bare
`.get(word)` and skips misses). Schema stays compatible unless explicitly versioned.

**Example:**
```python
# builder.py — GT loop (copies the Snowball drop-OOV pattern)
from .text_cleaning import is_valid_token

for word, tf in writer.term_freq.items():
    if not is_valid_token(word):
        continue
    lemma = morfeusz.dominant_lemma.get(word)
    if lemma is None:          # was: .get(word, word) — the self-lemma fallback
        continue               # drop OOV; count it for oov_self_lemma_rate stat
    df = writer.doc_freq.get(word, 1)
    gt_records.append((word, lemma, tf, df))
```

### Pattern 4: Source-specific sanitize stays at ingestion (don't centralize it)

**What:** HTML-unescape (news CSV, wiki), Wolne Lektury boilerplate patterns, and
URL/e-mail handling live in `text_sources.py` per-generator code — NOT in the shared
`clean_text`, which stays source-agnostic (NFC → `�`/control strip → foreign-token
excision → quote/dash normalize → whitespace collapse).

**When to use:** Phase D source hardening.
**Trade-offs:** Keeps `clean_text` pure, deterministic, and unit-testable with the
fixture table (`Béziera`, `Schrödinger`, `café`, `COVID-19`, …). Source quirks compose
by calling `html.unescape` etc. before `clean_text` in the relevant generator only.

## Data Flow

### Pipeline Flow (after hardening)

```
raw source bytes
    ↓  (per-generator sanitize: html.unescape / boilerplate / URL — Phase D)
clean_text(paragraph)                          ← Layer 1: sizing accuracy
    ↓
chunk_text_stream (counts CLEAN words → ~500-word docs hold)
    ↓
iter_*_docs (seen-hash dedup guard kills re-pass duplicates)
    ↓
add_document: clean_text(doc)                  ← Layer 2: CORRECTNESS GATE (idempotent)
    ├── writestr(cleaned)          stored docs  ─┐
    ├── tokenize(cleaned) → TF/DF  counts       ─┤── all three agree by construction
    └── resolve_homonyms(TF) → GT loop          ─┘    (drop OOV/invalid)
            ↓
paradigm batches (dictionary-filtered forms + assert is_valid_token)
            ↓
GT parquet + lemma-stratified splits + build_summary.json (+3 audit stats)
```

### Key Data Flows

1. **Doc flow:** generators → chunker → writer → `corpus.zip`. Cleaning touches it at
   both ends (paragraph pre-clean, doc gate); the chunker in the middle stays dumb.
2. **Count flow:** `tokenize(cleaned doc)` → `term_freq`/`doc_freq`. Counts can only
   contain tokens that literally appear in stored docs — the audit's root-cause
   invariant ("clean before both write and count").
3. **GT flow:** `term_freq` keys ∩ shared validator ∩ `dominant_lemma` → rows. Every GT
   word is therefore (a) in stored docs, (b) orthographically valid, (c) lemmatized —
   no fragment rows, no identity rows.
4. **Dictionary flow (unchanged):** PoliMorf ingest keeps its proper-noun/POS filters
   but imports the shared `VALID_WORD_RE` instead of its local copy — dictionary
   vocabulary and corpus vocabulary finally derive from one definition.

### Why NOT the alternatives (placement reasoning)

| Candidate seam | Verdict | Reason |
|----------------|---------|--------|
| Ingestion only (`text_sources.py`) | Insufficient | 4 generators + shared NKJP helper = 5+ edit points, easy to miss one; seed-doc fallback in `builder.py:182` bypasses ingestion entirely → no single guarantee |
| Chunking (`chunk_text_stream`) | Wrong layer | Chunker is a shared pure assembler; adding cleaning mixes concerns, and it still wouldn't cover seed docs or fix the GT fallback |
| Archive-write (`add_document`) | **Primary gate** | Single choke point every stored doc passes through; clean-once-then-write-and-count makes agreement structural, not conventional |
| GT export only | Symptom fix | Would hide fragments from GT while leaving them in stored docs and TF/DF for stemgen to train on |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| quick-test (20 docs) | No change; regression tests run here |
| compact (4.4k docs / 2.2M tokens) | No change; per-string cleaning is O(n) regex, dwarfed by gzip/zip I/O |
| recommended / extended (10–25k docs / 5–12.5M tokens) | No change; streaming preserved (generators yield `str`, never accumulate); module-level compiled regexes, no per-call `re.compile`; `seen`-hash dedup is the only new memory — bounded (store hashes, cap or fail-fast if source is pathologically small) |

### Scaling Priorities

1. **First bottleneck:** unchanged — network fetch + Morfeusz ingest + zip compression
   dominate wall time. Cleaning adds ~4–6 linear regex passes per paragraph/doc.
2. **Second bottleneck:** `term_freq`/`doc_freq` Counters (in-memory by design, pre-existing).
   Cleaning *reduces* unique-vocabulary pressure slightly by eliminating fragment types.

## Anti-Patterns

### Anti-Pattern 1: Clean after counting (or clean only one of write/count)

**What people do:** Insert `clean_text` before `writestr` but leave
`TOKEN_RE.findall(text)` on the raw variable (or vice versa).
**Why it's wrong:** Recreates the exact audit bug with the signs flipped — stored docs
and TF/DF diverge, fragments persist in whichever side still sees raw text.
**Do this instead:** Rebind once (`text = clean_text(text)`) as the first line of
`add_document`; every later use in the method automatically agrees.

### Anti-Pattern 2: Per-source duplicated cleaning regexes

**What people do:** Copy foreign-letter/quote/dash regexes into each of the 4 generators.
**Why it's wrong:** 4 copies drift (the current `TOKEN_RE`/`VALID_WORD_RE` split-vs-reject
divergence is this failure mode, already in production). One fix doesn't propagate.
**Do this instead:** All shared character-class logic lives in `text_cleaning.py`;
generators contain only source-specific calls (`html.unescape`, boilerplate matchers).

### Anti-Pattern 3: Stateful cleaner class

**What people do:** Build a `TextCleaner` object holding config/state threaded through
generators → chunker → writer.
**Why it's wrong:** The pipeline passes plain `Iterator[str]` between stages; threading
an object through 4 generators + chunker + writer rewrites every signature for zero
benefit — cleaning is a pure function of the string.
**Do this instead:** Module-level pure functions; any policy knobs are module constants
or explicit `clean_text(text, ...)` kwargs. Stats (foreign/digit rates) are computed by
separate audit helpers over finished outputs, not accumulated inside the cleaner.

### Anti-Pattern 4: Cleaning inside the chunker

**What people do:** Put `clean_text` in `chunk_text_stream` because "all docs pass through it."
**Why it's wrong:** Seed docs bypass the chunker (`builder.py:182` feeds strings straight
to `add_documents_for_genre`), and the chunker would gain a second responsibility,
complicating its word-target contract.
**Do this instead:** Keep the chunker a pure assembler over pre-cleaned paragraphs;
enforce at the writer.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| stemgen (consumer) | Document shared tokenizer contract (`TOKEN_RE` + `is_valid_token` semantics) alongside GT export | PROJECT.md requirement; stemgen's own tokenizer must match or training/eval vocabularies diverge again |
| PoliMorf / Morfeusz ingest | Unchanged data source; `morfeusz_extractor.py` imports shared validator | No re-ingest needed for the regex swap — same character class, single owner |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `text_sources` ↔ `corpus_sampler` | `Iterator[str]` (unchanged) | Pre-cleaned paragraphs flow; chunker signature untouched |
| `corpus_sampler` ↔ `builder` | `BalancedCorpusWriter` API (unchanged) | Gate is internal to `add_document`; `add_paradigm_batch` gains 1-line assert |
| `builder` ↔ `benchmark_splitter` | `list[(word, lemma, tf, df)]` (unchanged) | Main GT loop adopts Snowball's drop-OOV convention; schema stable |
| `writer.term_freq` → `resolve_homonyms` | `lemma_frequency_fn` callback (unchanged) | Frequencies are now fragment-free, so homonym ranking improves for free |

## Sources

- Repo source (HIGH confidence, read directly): `src/polish_corpus/corpus_sampler.py`
  (`add_document:73-91`, `TOKEN_RE:20`, `add_paradigm_batch:109-126`),
  `text_sources.py` (4 generators + `while count < max_docs` re-pass loops),
  `builder.py` (GT loop `:207-211`, seed fallback `:178-183`, summary `:267-279`),
  `morfeusz_extractor.py` (`VALID_WORD_RE:23`, ingest filters `:84-98`),
  `paradigm_generator.py` (reads `writer.term_freq`, writes via `add_paradigm_batch`),
  `benchmark_splitter.py` (Snowball drop-OOV `:67-69` — the pattern to copy),
  `config.py` (`GENRE_CONFIG`, `TIERS`, `CORE_POS_TAGS`).
- `quality-audit.md` (2026-10-16): root-cause analysis, truncation fixture table,
  per-source evidence, remediation Phases A–D.
- `.planning/PROJECT.md`: strict Polish-only direction, schema-compatibility and
  streaming constraints, phase scope A–D.

---
*Architecture research for: Corpus Quality Hardening (stemgen-polish-corpus)*
*Researched: 2026-10-16*
