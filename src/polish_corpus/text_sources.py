"""Real multi-genre Polish text streams for balanced corpus generation.

Extracts genuine Polish text across 4 genres according to general_polish_corpus_strategy.md:
- 01_nkjp_spoken_forum: Spoken transcripts, Sejm parliamentary speeches, internet forum text (from NKJP1M)
- 02_nkjp_literature: Classic and narrative Polish prose (from Wolne Lektury digital library)
- 03_nkjp_news: Modern journalism and press articles (from Polish news corpus)
- 04_wikipedia: Encyclopedic articles from Polish Wikipedia (from WikiNeural Polish slice)
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path

from .config import CACHE_DIR
from .corpus_sampler import chunk_text_stream

# Wolne Lektury export boilerplate: headers, footers, chapter markers,
# page numbers, separators, editor notes, end markers.
_BOILERPLATE_RES = (
    re.compile(r"^\s*(rozdzia[łl]|[rc]zapter|c[zr]ęść|tom|ksi[ęe]ga|pie[śs][ńn])\b[\s\divxlc]*\.?\s*$", re.I),
    re.compile(r"^\s*[MDCLXVI]+\.?\s*$"),
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*([*=\-#~_])\1{2,}\s*$"),
    re.compile(r"^\s*(przypis|uwaga|przyp\.)\b", re.I),
    re.compile(r"\*\*\*\s*(koniec|end)", re.I),
)

_BOILERPLATE_SUBSTRINGS = (
    "Udostępnione przez",
    "Czytaj dalej",
    "Pobierz",
    "ISBN",
    "Wolne Lektury",
    "Ten utwór",
)


def _is_boilerplate(line: str) -> bool:
    """Return True if a Wolne Lektury line is export boilerplate, not prose."""
    if not line:
        return False
    for sub in _BOILERPLATE_SUBSTRINGS:
        if sub in line:
            return True
    # Structural patterns only apply to short lines so mid-sentence
    # prose mentioning rozdział is never dropped.
    if len(line) >= 80:
        return False
    try:
        return any(rx.search(line) for rx in _BOILERPLATE_RES)
    except re.error:
        return False


def _stream_nkjp_sentences(jsonl_gz_path: Path, channel_prefixes: tuple[str, ...]) -> Iterator[str]:
    """Stream reassembled sentences from NKJP1M jsonl.gz matching channel prefixes."""
    if not jsonl_gz_path.exists():
        return
    with gzip.open(jsonl_gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line:
                continue
            data = json.loads(line)
            tid = data.get("nkjp_text", "")
            # Check channel prefix (e.g. NKJP_1M_6... for spoken, NKJP_1M_1... for press)
            clean_tid = tid.replace("NKJP_1M_", "")
            if any(clean_tid.startswith(p) for p in channel_prefixes):
                tokens = data.get("tokens", [])
                if tokens:
                    sentence = " ".join(tokens)
                    # Simple punctuation spacing fix
                    sentence = re.sub(r"\s+([,.:;?!])", r"\1", sentence)
                    sentence = re.sub(r"([(\"«])\s+", r"\1", sentence)
                    yield sentence


def iter_spoken_forum_docs(max_docs: int) -> Iterator[str]:
    """Yield natural ~500-word documents for 01_nkjp_spoken_forum."""
    train_path = CACHE_DIR / "nkjp1m_train.jsonl.gz"
    dev_path = CACHE_DIR / "nkjp1m_dev.jsonl.gz"

    def _sentences():
        spoken_prefixes = ("6", "7", "4", "sca", "Supe")
        yield from _stream_nkjp_sentences(train_path, spoken_prefixes)
        yield from _stream_nkjp_sentences(dev_path, spoken_prefixes)

    count = 0
    seen: set[str] = set()
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


def iter_literature_docs(max_docs: int) -> Iterator[str]:
    """Yield natural ~500-word documents for 02_nkjp_literature from Wolne Lektury."""
    lit_dir = CACHE_DIR / "literature"

    def _paragraphs():
        if lit_dir.exists():
            for book_file in sorted(lit_dir.glob("*.txt")):
                with open(book_file, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if _is_boilerplate(line):
                            continue
                        if len(line) > 20:
                            yield line

        train_path = CACHE_DIR / "nkjp1m_train.jsonl.gz"
        yield from _stream_nkjp_sentences(train_path, ("2",))

    count = 0
    seen: set[str] = set()
    while count < max_docs:
        doc_iter = chunk_text_stream(_paragraphs(), target_words=500, min_words=250)
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


def iter_news_docs(max_docs: int) -> Iterator[str]:
    """Yield natural ~500-word documents for 03_nkjp_news from news corpus & NKJP press."""
    news_csv_1 = CACHE_DIR / "news_articles.csv"
    news_csv_2 = CACHE_DIR / "news_test.csv"

    def _articles():
        for csv_path in (news_csv_1, news_csv_2):
            if csv_path.exists():
                with open(csv_path, encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    next(reader, None)  # Skip header
                    for row in reader:
                        if len(row) > 1 and row[1]:
                            yield row[1].strip()

        train_path = CACHE_DIR / "nkjp1m_train.jsonl.gz"
        yield from _stream_nkjp_sentences(train_path, ("1",))

    count = 0
    seen: set[str] = set()
    while count < max_docs:
        doc_iter = chunk_text_stream(_articles(), target_words=500, min_words=200)
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


def iter_wikipedia_docs(max_docs: int) -> Iterator[str]:
    """Yield natural ~500-word documents for 04_wikipedia from WikiNeural."""
    wiki_path = CACHE_DIR / "wiki_pl.jsonl"

    def _sentences():
        if wiki_path.exists():
            with open(wiki_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line:
                        continue
                    data = json.loads(line)
                    tokens = data.get("tokens", [])
                    if tokens:
                        sentence = " ".join(tokens)
                        sentence = re.sub(r"\s+([,.:;?!])", r"\1", sentence)
                        sentence = re.sub(r"([(\"«])\s+", r"\1", sentence)
                        yield sentence

    count = 0
    seen: set[str] = set()
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
