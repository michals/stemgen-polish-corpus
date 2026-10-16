---
phase: 01-cleaning-stage-shared-tokenizer
reviewed: 2026-10-16T19:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/polish_corpus/text_cleaning.py
  - src/polish_corpus/corpus_sampler.py
  - tests/test_cleaning.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-10-16T19:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 1 tracer slice plus expansion (`text_cleaning.py` sole-owner
module, writer-boundary gate in `corpus_sampler.py`, 40-case regression battery
in `tests/test_cleaning.py`) against the locked ordering (NFC-first, unescape
before filter, filter before normalize) and the threat models T-01-01, T-01-SC,
T-01-02. The architecture is sound — single choke point, shared tokenizer,
stored-text/count agreement holds on every probe — and `pytest` (41 passed,
1 skipped) plus `ruff check` are green. No security issues: stdlib only
(T-01-SC holds), regexes are bounded char classes with no backtracking shape
(T-01-01 holds), single-pass unescape (T-01-02 holds).

Adversarial probing with executed repros nevertheless found one **blocker**:
entity-encoded combining marks (`cafe&#769;`) pass through NFC (which runs
*before* `html.unescape`), are invisible to the drop filter (it only inspects
`L`-category chars), and are salvaged by `TOKEN_RE` into a countable `cafe`
fragment — the exact `café→caf` truncation shape this phase exists to kill,
in both stored text and TF/DF. Four warnings (stripped-char reintroduction via
char refs, single-hyphen `TOKEN_RE` splitting multi-compounds, chunker sizing
on uncleaned fragment counts, empty-after-clean docs consuming quota) and three
info items round out the report. Every finding below was verified by executing
the current code, not by reading alone.

## Critical Issues

### CR-01: Entity-encoded combining marks evade NFC and the foreign-token filter, salvaging countable fragments

**File:** `src/polish_corpus/text_cleaning.py:84-103`
**Issue:** `clean_text()` runs NFC normalization (step 1, line 84) *before*
`html.unescape` (step 3, line 94). A combining accent introduced by a numeric
character reference therefore never sees NFC, and `_drop_token()` (lines 41-52)
only inspects `L`-category characters, so combining marks (`Mn`) never trigger
a drop. Verified repro against the current code:

```python
clean_text("słowo cafe&#769; inne")   # -> 'słowo cafe\u0301 inne'
tokenize(clean_text("słowo cafe&#769; inne"))  # -> ['słowo', 'cafe', 'inne']
```

The foreign token's base letters survive as the countable fragment `cafe` in
both stored text and TF/DF — a direct violation of the must-have truth
"tokens with non-Polish diacritics vanish entirely (no split fragments like
`caf` in docs or counts)". The same root cause salvages base letters from
*literal* decomposed sequences with no NFC precomposition:

```python
clean_text("słowo q\u0301x inne")     # -> 'słowo q\u0301x inne' (kept)
tokenize(...)                          # -> ['słowo', 'q', 'x', 'inne']
```

The existing NFD test only covers composable input (`cafe\u0301` → `café`),
so neither path is pinned.
**Fix:** Re-apply NFC after unescaping, and drop tokens containing any
combining mark, so marks can never act as invisible glue:

```python
cleaned = html.unescape(cleaned)
# Re-normalize: unescape can introduce decomposed sequences (e.g. e + U+0301
# from &#769;) that must compose BEFORE the foreign-token filter.
cleaned = unicodedata.normalize("NFC", cleaned)
```

and in `_drop_token`, inside the per-char loop:

```python
# 3. Any combining mark kills the whole token: marks without an NFC
#    precomposition (or introduced post-NFC via entities) must never
#    leave their base letters behind as salvageable fragments.
if unicodedata.category(ch).startswith("M"):
    return True
```

Add regression pins for `cafe&#769;` and a non-composable `q\u0301x` case
asserting `tokenize(...) == ["słowo", "inne"]`.

## Warnings

### WR-01: Character references reintroduce already-stripped characters after the strip step

**File:** `src/polish_corpus/text_cleaning.py:85-94`
**Issue:** The U+FFFD/control-char strip (step 2) runs *before* `html.unescape`
(step 3), so encoded forms of stripped characters are decoded after the strip
has run and survive into stored docs. Verified:

```python
clean_text("słowo &#0; inne")      # -> 'słowo \ufffd inne'  (U+FFFD reintroduced;
                                  #    html.unescape maps &#0; per HTML5 to FFFD)
clean_text("słowo &#xFFFD; inne")  # -> 'słowo \ufffd inne'
```

This violates the pinned "control characters and `�` vanish" guarantee for any
source containing char refs (the test battery only exercises literal controls
and literal FFFD). Control refs such as `&#1;` pass through similarly.
**Fix:** Move the strip to after `html.unescape` (ordering becomes
NFC → unescape → NFC → strip → filter, which also composes CR-01's fix
naturally), so every decoded character faces both the strip and the filter:

```python
# 2. Decode HTML entities FIRST, so decoded controls/FFFD/combining
#    marks still face the NFC + strip + filter steps below.
cleaned = html.unescape(cleaned)
cleaned = unicodedata.normalize("NFC", cleaned)
cleaned = "".join(
    ch
    for ch in cleaned
    if ch in ("\n", "\t")
    or (ch != "\ufffd" and not unicodedata.category(ch).startswith("C"))
)
```

Pin with `clean_text("słowo &#0; inne") == "słowo inne"` and an
`&#xFFFD;` case.

### WR-02: TOKEN_RE accepts only one hyphen, splitting multi-compounds and disagreeing with is_valid_token

**File:** `src/polish_corpus/text_cleaning.py:18`
**Issue:** `TOKEN_RE` allows at most one hyphen group
(`(?:-...)?`), while `is_valid_token()` (lines 65-70) validates an arbitrary
number of hyphen segments. A triple compound is therefore split into two
countable tokens while the validator rejects the whole — verified:

```python
tokenize("biało-czerwono-zielony")          # -> ['biało-czerwono', 'zielony']
is_valid_token("biało-czerwono-zielony")     # -> False
```

One orthographic word becomes two TF/DF entries (TF inflation), and
`clean_text` keeps the whole compound in stored text while counts record two
tokens. (`morfeusz_extractor.VALID_WORD_RE` shares the single-hyphen shape, so
no cross-module divergence today — but the two validators disagree with each
other inside this module.)
**Fix:** Allow repeated hyphen groups so the extractor and the validator agree:

```python
TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)*")
```

Pin with `tokenize("x biało-czerwono-zielony y") == ["x", "biało-czerwono-zielony", "y"]`
and `is_valid_token("biało-czerwono-zielony")`.

### WR-03: chunk_text_stream sizes and filters on uncleaned fragment counts

**File:** `src/polish_corpus/corpus_sampler.py:34-40`
**Issue:** `chunk_text_stream` calls `count_words()` (shared `tokenize()`) on
*raw* paragraphs, upstream of the writer gate. `tokenize` on dirty text counts
the very fragments the gate later drops — verified `count_words("Béziera café")
== 3` (fragments `B`, `ziera`, `caf`), all of which vanish in `add_document`.
Consequences: (a) ~500-word doc-size targeting is systematically inflated by
foreign-fragment counts, so cleaned docs undershoot the target; (b) the
`para_words == 0` skip-empty path (line 39) catches only numeric-only
paragraphs (`2012 !!!` → 0 words) while foreign-diacritic-only paragraphs
(`Béziera café` → 3 phantom words) flow into docs as blank residue. The
empty-after-clean test pins only the numeric sub-case.
**Fix:** Clean before counting in the chunker (verified `clean_text` is
idempotent on representative inputs, so the writer gate re-cleaning is safe):

```python
from .text_cleaning import clean_text, tokenize
...
for para in paragraphs:
    para_clean = clean_text(para.strip())
    if not para_clean:
        continue
    para_words = count_words(para_clean)
```

This makes sizing, skip-empty, stored text, and TF/DF all derive from the same
cleaned text. Pin with a foreign-only paragraph (`"Béziera café"` →
skipped) and a sizing test with mixed dirty input.

### WR-04: Empty-after-clean docs are written as zero-byte entries and consume genre quota

**File:** `src/polish_corpus/corpus_sampler.py:70-92`
**Issue:** When a doc cleans down to `""`, `add_document` still increments
`doc_counts`, writes a zero-byte `doc_*.txt` into `corpus.zip`, and returns the
filename indistinguishably from a real doc. Worse, `add_documents_for_genre`
(lines 100-107) counts every call toward `max_docs`, so a foreign-heavy genre
fills its quota with empty files instead of real documents — silently
degrading corpus content while all counters look healthy. The test at
`tests/test_cleaning.py:189-196` pins `stored == ""` rather than a skip, so
the behavior is locked in by regression test.
**Fix:** Skip the write (and the quota consumption) when cleaning yields
nothing, returning a sentinel the caller can distinguish:

```python
text = clean_text(text)
if not text:
    # Nothing countable survived cleaning: do not consume a doc slot
    # or write an empty entry into the archive.
    return ""
```

Update the empty-after-clean test to assert no file is written, no counters
move, and `add_documents_for_genre` keeps pulling until `max_docs` real docs
(or source exhaustion) rather than stopping at empty ones.

## Info

### IN-01: summary() annotates with builtin `any` instead of `Any`

**File:** `src/polish_corpus/corpus_sampler.py:132`
**Issue:** `def summary(self) -> dict[str, any]:` uses the builtin function
`any` as a type annotation. It works at runtime but is a type error in intent
and will confuse type checkers.
**Fix:** `from typing import Any` and annotate `-> dict[str, Any]:`.

### IN-02: add_paradigm_batch bypasses the shared tokenizer by documented design

**File:** `src/polish_corpus/corpus_sampler.py:109-126`
**Issue:** The paradigm path counts `[t.lower() for t in forms]` directly
instead of via shared `tokenize()`, so the phase headline "single shared
tokenizer for all counting" holds only for the `add_document` path. No defect
today (dictionary forms are pre-validated by `VALID_WORD_RE`), and the plan
explicitly scoped this path out — recorded here so a future change to either
regex re-checks this second counting site.
**Fix:** No change required; if `TOKEN_RE` is ever widened (see WR-02), mirror
the change in `VALID_WORD_RE` or route paradigm forms through `tokenize()`.

### IN-03: Double-encoded entities leave a countable literal (accepted residual)

**File:** `src/polish_corpus/text_cleaning.py:94`
**Issue:** `&amp;eacute;` decodes single-pass to the literal `&eacute;`, which
survives the filter and contributes a countable `eacute` token (verified:
`tokenize(...) == ['słowo', 'eacute', 'inne']`). This is the explicitly
accepted T-01-02 disposition (single-pass decoding, no recursive expansion),
not a bug — recorded so the residual is visible.
**Fix:** None required by the threat model; if entity-heavy sources show
`eacute`-style tokens in audit stats, consider a second targeted pass that
drops bare `&...;` remnants.

---

_Reviewed: 2026-10-16T19:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
