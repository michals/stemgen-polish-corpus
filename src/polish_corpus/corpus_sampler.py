"""Multi-genre balanced corpus sampler and document chunker.

Implements Step 2 of general_polish_corpus_strategy.md:
- Generates ~400-600 words per .txt document to match natural Zipfian TF and DF.
- Balances genre quotas (spoken/forum, literature, news, wikipedia).
- Streams documents directly into the destination corpus.zip archive.
"""

from __future__ import annotations

import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .config import GENRE_CONFIG
from .text_cleaning import audit_clean, clean_text, tokenize


def _audit_rate_entry(counts: Counter) -> dict[str, int | float | bool]:
    """Derive input-honest audit rates from raw per-genre/global counters."""
    foreign_dropped = counts.get("foreign_dropped", 0)
    digit_dropped = counts.get("digit_dropped", 0)
    tokens_kept = counts.get("tokens_kept", 0)
    dropped_total = foreign_dropped + digit_dropped
    denom = dropped_total + tokens_kept
    return {
        "foreign_fragment_rate": (foreign_dropped / denom) if denom else 0.0,
        "digit_token_rate": (digit_dropped / denom) if denom else 0.0,
        "dropped_total": dropped_total,
        "foreign_dropped": foreign_dropped,
        "digit_dropped": digit_dropped,
        "tokens_kept": tokens_kept,
        "url_removed": counts.get("url_removed", 0),
        "email_removed": counts.get("email_removed", 0),
    }


def count_words(text: str) -> int:
    """Return count of alphabetic word tokens in text."""
    return len(tokenize(text))


def chunk_text_stream(
    paragraphs: Iterator[str],
    target_words: int = 500,
    min_words: int = 250,
) -> Iterator[str]:
    """Assemble paragraphs into documents of approximately `target_words` length."""
    current_doc: list[str] = []
    current_word_count = 0

    for para in paragraphs:
        # 1. Clean BEFORE counting so sizing, skip-empty, stored text, and
        #    TF/DF all derive from the same cleaned text (clean_text is
        #    idempotent, so the writer gate re-clean is safe).
        para_clean = clean_text(para.strip())
        if not para_clean:
            continue
        para_words = count_words(para_clean)
        if para_words == 0:
            continue

        current_doc.append(para_clean)
        current_word_count += para_words

        if current_word_count >= target_words:
            yield "\n\n".join(current_doc)
            current_doc = []
            current_word_count = 0

    if current_doc and current_word_count >= min_words:
        yield "\n\n".join(current_doc)


class BalancedCorpusWriter:
    """Writes chunked documents into a hierarchical corpus.zip archive."""

    def __init__(self, output_zip_path: Path):
        self.output_zip_path = Path(output_zip_path)
        self.output_zip_path.parent.mkdir(parents=True, exist_ok=True)
        self.zip_file = zipfile.ZipFile(
            self.output_zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        )
        self.doc_counts: dict[str, int] = {genre: 0 for genre in GENRE_CONFIG}
        self.token_counts: dict[str, int] = {genre: 0 for genre in GENRE_CONFIG}
        self.audit_counts: dict[str, Counter] = {genre: Counter() for genre in GENRE_CONFIG}
        self.term_freq: Counter[str] = Counter()
        self.doc_freq: Counter[str] = Counter()

    def add_document(self, genre: str, text: str) -> str:
        """Add a single natural document to the zip archive under genre directory."""
        # Single choke-point gate: audit_clean BEFORE both the archive write
        # and TF/DF counting so stored docs and counts agree by construction.
        # Audit counters accumulate HERE ONLY (never in chunk_text_stream), so
        # sizing-path drops cannot double-count into the reported rates.
        text, counts = audit_clean(text)
        if genre not in self.audit_counts:
            self.audit_counts[genre] = Counter()
        self.audit_counts[genre].update(counts._asdict())
        if not text:
            # Nothing countable survived cleaning: do not consume a doc slot
            # or write an empty entry into the archive (drops above are still
            # recorded so rates stay input-honest).
            return ""
        if genre not in self.doc_counts:
            self.doc_counts[genre] = 0
            self.token_counts[genre] = 0

        self.doc_counts[genre] += 1
        doc_idx = self.doc_counts[genre]
        filename = f"{genre}/doc_{doc_idx:05d}.txt"

        tokens = [t.lower() for t in tokenize(text)]
        token_count = len(tokens)
        self.token_counts[genre] += token_count

        # Track vocabulary frequencies
        self.term_freq.update(tokens)
        self.doc_freq.update(set(tokens))

        self.zip_file.writestr(filename, text)
        return filename

    def add_documents_for_genre(
        self,
        genre: str,
        docs: Iterator[str],
        max_docs: int,
    ) -> int:
        """Add up to max_docs documents for a specific genre."""
        count = 0
        for doc in docs:
            # Empty-after-clean docs return "" and do not consume quota:
            # keep pulling until max_docs real docs or source exhaustion.
            if not self.add_document(genre, doc):
                continue
            count += 1
            if count >= max_docs:
                break
        return count

    def add_paradigm_batch(self, batch_idx: int, forms: list[str]) -> str:
        """Add a batch of inflected paradigm forms to 99_morfeusz_paradigms/."""
        genre = "99_morfeusz_paradigms"
        if genre not in self.doc_counts:
            self.doc_counts[genre] = 0
            self.token_counts[genre] = 0

        self.doc_counts[genre] += 1
        filename = f"{genre}/paradigm_{batch_idx:04d}.txt"

        # Group forms into readable punctuated chunks of ~15 words ending in a period
        # so downstream neural taggers (spaCy / Stanza) do not overflow sequence tagger buffers
        chunks = []
        chunk_size = 15
        for i in range(0, len(forms), chunk_size):
            slice_forms = forms[i : i + chunk_size]
            chunks.append(", ".join(slice_forms) + ".")
        text = "\n".join(chunks) + "\n"

        tokens = [t.lower() for t in forms]
        self.token_counts[genre] += len(tokens)
        self.term_freq.update(tokens)
        self.doc_freq.update(set(tokens))

        self.zip_file.writestr(filename, text)
        return filename

    def close(self) -> None:
        """Close the zip archive."""
        self.zip_file.close()

    def summary(self) -> dict[str, Any]:
        """Return compilation summary metrics."""
        global_counts: Counter = Counter()
        for genre_counts in self.audit_counts.values():
            global_counts.update(genre_counts)
        return {
            "total_documents": sum(self.doc_counts.values()),
            "total_tokens": sum(self.token_counts.values()),
            "unique_vocabulary": len(self.term_freq),
            "genre_docs": dict(self.doc_counts),
            "genre_tokens": dict(self.token_counts),
            "archive_size_bytes": self.output_zip_path.stat().st_size if self.output_zip_path.exists() else 0,
            "audit_rates": {
                "global": _audit_rate_entry(global_counts),
                "per_genre": {genre: _audit_rate_entry(counts) for genre, counts in self.audit_counts.items()},
                "paradigm_docs_excluded": True,
            },
        }
