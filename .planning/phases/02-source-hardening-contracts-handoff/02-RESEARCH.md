# Phase 2: Source Hardening + Contracts + Handoff — Research

**Researched:** 2026-10-16 · **Domain:** source sanitizers + dedup guard + docs-only contracts · **Confidence:** HIGH

Locked: GT export code untouched (`builder.py:205-236` OOV fallback stays; DOC-01 documents it), no stemgen repo changes (TOK-03 docs only), stdlib only, streaming (no full-corpus in-memory). Builds on Phase 1 `text_cleaning.py` choke point — stored docs and TF/DF agree by construction.

## 1. SRC-01 — Dedup guard: exact insertion points

**Bug:** every `iter_*_docs` in `text_sources.py` wraps `chunk_text_stream(...)` in `while count < max_docs` with a fresh generator each pass (`:56-66, :90-100, :122-132, :154-164`). When the source yields fewer docs than quota, pass 2 re-chunks the identical finite stream and re-yields byte-identical docs. Duplicates inflate `doc_freq` (DF skew) and waste archive space. WikiNeural/small literature caches hit this first.

**Fix:** content-hash seen-guard inside each iterator's yield loop. Shape (same in all four iterators):

```python
seen: set[str] = set()
count = 0
while count < max_docs:
    doc_iter = chunk_text_stream(_sentences(), target_words=500, min_words=200)
    yielded_in_pass = 0
    for doc in doc_iter:
        digest = hashlib.blake2b(doc.encode("utf-8"), digest_size=16).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        yield doc
        count += 1
        yielded_in_pass += 1
        if count >= max_docs:
            return
    if yielded_in_pass == 0:
        break
```

Notes: `hashlib` is stdlib (no new dep). 16-byte blake2b digests × quota docs (thousands) — bounded, no memory concern. `seen` lives per-iterator-call (function local), not module global — no cross-build leakage. Seed fallback in `builder.py:182` needs no guard (docs carry `Dokument numer {i+1}`, distinct by construction). Empty-after-clean docs never reach the guard (`add_documents_for_genre` skips `""` without consuming quota, `corpus_sampler.py:108-117`).

**Test:** feed a 2-doc source with `max_docs=5`, assert exactly 2 docs yielded and no repeats.

## 2. SRC-03 — URL/e-mail: strip inside `clean_text()`, not in genre paths

**Bug:** `http://example.com/foo` tokenizes via `TOKEN_RE` into `http`/`example`/`com` — all Polish-class letters, all countable. Same for `user@domena.pl` → `user`/`domena`/`pl`. News CSVs (`row[1]`) and WikiNeural tokens are the live paths; forum text (NKJP spoken/forum channels) can also carry URLs.

**Decision:** strip at the `clean_text()` choke point (new step before token-drop), NOT per-genre helpers. Rationale: single choke point keeps docs/counts agreement by construction (Phase 1 invariant); covers all four genres including forum URLs for free; `chunk_text_stream` already cleans before sizing (`corpus_sampler.py:38`), so sizing stays consistent.

**Regexes** (simple, no nested quantifiers — no ReDoS shape):

```python
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.?[\w.]+")
```

Applied as `cleaned = _URL_RE.sub(" ", cleaned)` then `_EMAIL_RE.sub(" ", cleaned)`, positioned AFTER unescape/control-strip (encoded forms like `&#64;` must decode to `@` first) and BEFORE the token-level DROP. Trailing punctuation (`.,;)`) attached to a URL is consumed by `\S+` — acceptable (punctuation is not countable anyway). Must not eat valid Polish: `@` and `://` never occur in Polish prose.

**Phase 1 regression risk:** additive step, existing 41 tests must stay green — URL/email patterns are disjoint from Polish prose. `add_paradigm_batch` untouched (forms list, no URLs).

**Tests:** `https://example.com/artykuł o kocie` → URL gone, `artykule?` Polish retained; `napisz na adres jan@domena.pl proszę` → email gone, surroundings retained; URL-only paragraph → `""` flows through existing skip-empty path.

## 3. SRC-02 — Wolne Lektury boilerplate: `_is_boilerplate()` helper

**Current filter** (`text_sources.py:79-82`) drops only three literal cases: `Ten utwór…`, `ISBN `, `Wolne Lektury`. WL `.txt` files also carry: title/author headers, `Rozdział N` / `ROZDZIAŁ` / Roman-numeral-alone lines (`XVII`), page numbers (digit-only lines), separator lines (`***`, `===`, `---`), editor footnotes (`Przypis:`, `Uwaga edytora`), START/END markers (`*** KONIEC ***`, `Początek...`).

**Design:** module-level `_is_boilerplate(line: str) -> bool` in `text_sources.py`, checked per line before the `len(line) > 20` yield gate:

```python
_BOILERPLATE_RES = (
    re.compile(r"^\s*(rozdzia[łl]|[rc]zapter|c[zr]ęść|tom|księga|pieśń)\b[\s\divxlc]*\.?\s*$", re.I),
    re.compile(r"^\s*[MDCLXVI]+\.?\s*$"),                    # roman-numeral-alone
    re.compile(r"^\s*\d+\s*$"),                              # page-number-alone
    re.compile(r"^\s*([*=\-#~_])\1{2,}\s*$"),                # separator runs
    re.compile(r"^\s*(przypis|uwaga|przyp\.)\b", re.I),      # editor notes
    re.compile(r"\*\*\*\s*(koniec|end)", re.I),              # end markers
)
```

Plus substring checks folded into the same helper: `Udostępnione przez`, `Czytaj dalej`, `Pobierz`, `ISBN`, `Wolne Lektury`, `Ten utwór`. **Over-drop guard:** structural regexes apply to short lines only (line length check inside helper, e.g. `< 80` chars) so multi-clause prose mentioning `rozdział` is never dropped; the existing `len(line) > 20` gate stays. Case-insensitive Polish-aware matching — no lowercase-then-compare pitfalls.

**Out of scope:** fuzzy/ML boilerplate detection, per-book templates — static regex set covers the known WL export format.

**Tests:** synthetic WL sample (header + `ROZDZIAŁ III` + `27` + `***` + prose paragraph) → only prose survives; prose containing `rozdział` mid-sentence retained.

## 4. TOK-03 — Tokenizer reuse contract (docs only)

New `docs/tokenizer-contract.md`: documents `TOKEN_RE` (exact pattern), `is_valid_token()` rules (fullmatch + no-digit + per-hyphen-segment Polish-only), `clean_text()` 7-step ordering with the load-bearing positions (unescape-before-filter, filter-before-normalize), `tokenize()` definition, a copy-paste reuse snippet for the stemgen side, and a version note (contract v1, pinned to this repo's `text_cleaning.py`). No code, no stemgen changes. Reference from the domain `README.md`? No — domain README is generated per-build by `builder.py`; the contract lives as a standalone repo doc.

## 5. DOC-01 — `ground-truth-issues.md` (docs only)

New repo-root `ground-truth-issues.md` capturing three audit findings with file:line evidence, explicitly NOT implemented here:
1. OOV self-lemma fallback — `builder.py:209` `morfeusz.dominant_lemma.get(word, word)` emits `(word, word)` identity rows that teach stemmer identity mappings.
2. Proper-noun leakage into counts — writer counts every `tokenize()` hit; Morfeusz proper-noun filtering lives in the dictionary ingest, not on the count path.
3. `oov_self_lemma_rate` proposal — report OOV-identity share in `build_summary.json` as the acceptance metric for the upstream fix.

## 6. Edge cases planner must handle

- Dedup digest must hash the **chunked doc** (post-`chunk_text_stream`), not raw paragraphs — identical paras legitimately recur across docs; doc-level identity is the invariant.
- URL-strip ordering vs entity-drop: `&eacute;`-style entities decode first, so `example&#46;com` inside a URL is consumed by `\S+` before it can decode into countable fragments — correct outcome either way.
- `chunk_text_stream` min_words gate unchanged; URL-only or boilerplate-only paras clean to `""`/zero-count and take the existing skip path (`corpus_sampler.py:39-43`).
- Full gates both plans share: `pytest tests/ -q`, `ruff check src/ tests/`.
