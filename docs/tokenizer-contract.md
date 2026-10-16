# Tokenizer Contract (v1)

Reuse contract for the shared Polish tokenizer owned by this repo.
The stemgen side can copy the pattern below without reading our source.
Pinned to `src/polish_corpus/text_cleaning.py` — if that module changes,
this contract needs a new version.

## Exact pattern

```python
TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)*")
```

Polish alphabet class: ASCII letters plus `ąćęłńóśźż` (both cases).
Hyphen compounds are single tokens: one or more `-segment` groups.

## `is_valid_token()` rules

A token is countable only if ALL hold:

1. Non-empty.
2. `TOKEN_RE.fullmatch(token)` matches (no partial matches).
3. No digits anywhere (`COVID-19`, `model3`, `2012` rejected).
4. Every hyphen segment is non-empty and Polish-only — `biało-czerwony`
   is retained while `Saint-Étienne` drops whole.

Source: `src/polish_corpus/text_cleaning.py:65-80`.

## `clean_text()` step ordering

Load-bearing positions — do not reorder:

1. NFC normalize FIRST (NFD combining marks must not evade the filter).
2. `html.unescape` BEFORE strip/filter (decoded controls/marks still face later steps).
3. Re-normalize NFC (unescape can introduce decomposed sequences, e.g. `e` + U+0301).
4. Strip U+FFFD and control chars (keep `\n`, `\t`).
5. Strip URLs (`https?://\S+`, `www.\S+`) and e-mail addresses — AFTER
   unescape (encoded `&#64;` decodes to `@` first), BEFORE the token DROP.
6. Token-level DROP on whitespace-delimited tokens: the whole token vanishes,
   no letter-part salvage (`café` never `caf`, `Béziera` never `B` + `ziera`).
7. Quote/dash normalization (`„ " " « »` → `"`, `— –` → `-`) AFTER the
   filter so dropped tokens are never laundered back into countable text.
8. Collapse whitespace, preserving paragraph breaks.

Source: `src/polish_corpus/text_cleaning.py:88-133`.

## `tokenize()` definition

```python
def tokenize(text: str) -> list[str]:
    """Split text into valid Polish word tokens."""
    return [t for t in TOKEN_RE.findall(text) if is_valid_token(t)]
```

## Reuse snippet (copy-paste for the stemgen side)

```python
import re

TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)*")
_POLISH_LETTER_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")


def is_valid_token(token: str) -> bool:
    if not token or TOKEN_RE.fullmatch(token) is None:
        return False
    if any(ch.isdigit() for ch in token):
        return False
    for segment in token.split("-"):
        if not segment or any(not _POLISH_LETTER_RE.fullmatch(ch) for ch in segment):
            return False
    return True


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text) if is_valid_token(t)]
```

Note: this snippet covers tokenization only. The full `clean_text()`
pipeline (NFC/entity/URL/drop ordering above) is what guarantees stored
text and counts agree — copy it whole from `text_cleaning.py` if you
need cleaning, not just tokenizing.

## Version note

Contract v1, 2026-10-16. Source of truth is `text_cleaning.py` in this
repo; any change to `TOKEN_RE`, `is_valid_token()`, or `clean_text()`
ordering supersedes this document until it is re-versioned.
