"""Shared Polish text cleaning and tokenization stage.

Implements Phase 1 of the corpus quality hardening milestone:
sole owner of TOKEN_RE/is_valid_token()/clean_text()/tokenize() so that
stored documents and TF/DF counts agree by construction. All consumers
(corpus_sampler writer gate, word counters) import from here; no local
TOKEN_RE copies elsewhere.
"""

from __future__ import annotations

import html
import re
import unicodedata

# Tokenization pattern matching valid Polish word tokens.
# Moved verbatim from corpus_sampler.py; this module is the sole owner.
TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)?")

# Single Polish-alphabet letter (ASCII + Polish diacritics).
_POLISH_LETTER_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")

# Quote/dash normalization applied AFTER the foreign-token filter so that
# dropped tokens are never laundered back into countable text.
_QUOTE_REPLACEMENTS = (
    ("„", '"'),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("«", '"'),
    ("»", '"'),
    ("—", "-"),
    ("–", "-"),
)


def _is_polish_letter(ch: str) -> bool:
    """Return True if a single character is a Polish-alphabet letter."""
    return _POLISH_LETTER_RE.fullmatch(ch) is not None


def _drop_token(token: str) -> bool:
    """Return True if a whitespace-delimited token must vanish whole."""
    for ch in token:
        # 1. Any digit kills the whole token (2012, COVID-19, model3).
        if ch.isdigit():
            return True
        # 2. Any non-Polish letter kills the whole token (é in café,
        #    É in Saint-Étienne). Punctuation attached to a Polish word
        #    (commas, quotes) is not a letter and does not trigger a drop.
        if unicodedata.category(ch).startswith("L") and not _is_polish_letter(ch):
            return True
    return False


def is_valid_token(token: str) -> bool:
    """Return True if a token is a countable Polish word token."""
    if not token:
        return False
    if TOKEN_RE.fullmatch(token) is None:
        return False
    if any(ch.isdigit() for ch in token):
        return False
    # 3. Every hyphen segment must be non-empty and Polish-only, so
    #    biało-czerwony is retained while Saint-Étienne drops whole.
    for segment in token.split("-"):
        if not segment:
            return False
        if any(not _is_polish_letter(ch) for ch in segment):
            return False
    return True


def tokenize(text: str) -> list[str]:
    """Split text into valid Polish word tokens."""
    return [t for t in TOKEN_RE.findall(text) if is_valid_token(t)]


def clean_text(text: str) -> str:
    """Clean raw corpus text, dropping foreign and numeric tokens whole."""
    if not text:
        return ""
    # 1. NFC normalize FIRST so NFD combining marks cannot evade the
    #    Polish-class test below.
    cleaned = unicodedata.normalize("NFC", text)
    # 2. Strip U+FFFD and control chars (keep newline/tab) BEFORE unescaping.
    cleaned = "".join(
        ch
        for ch in cleaned
        if ch in ("\n", "\t")
        or (ch != "\ufffd" and not unicodedata.category(ch).startswith("C"))
    )
    # 3. Decode HTML entities BEFORE the foreign-token filter, so that
    #    &eacute; becomes e and is then filtered, not passed through.
    cleaned = html.unescape(cleaned)
    # 4. Token-level DROP on whitespace-delimited tokens: the whole token
    #    vanishes, no letter-part salvage (Béziera drops entirely, never
    #    B+ziera; café never caf; COVID-19 never COVID). Whitespace
    #    separators are preserved so paragraph breaks survive.
    kept_parts = []
    for part in re.split(r"(\s+)", cleaned):
        if not part or part[0].isspace() or not _drop_token(part):
            kept_parts.append(part)
    cleaned = "".join(kept_parts)
    # 5. Quote/dash normalization AFTER the filter (never launder dropped
    #    tokens back into countable text).
    for old, new in _QUOTE_REPLACEMENTS:
        cleaned = cleaned.replace(old, new)
    # 6. Collapse whitespace, preserving paragraph breaks.
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
    cleaned = re.sub(r"[ ]*\n[ ]*", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
