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

from .config import GENRE_CONFIG
from .text_cleaning import clean_text, tokenize


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
        self.term_freq: Counter[str] = Counter()
        self.doc_freq: Counter[str] = Counter()

    def add_document(self, genre: str, text: str) -> str:
        """Add a single natural document to the zip archive under genre directory."""
        # Single choke-point gate: clean BEFORE both the archive write and
        # TF/DF counting so stored docs and counts agree by construction.
        text = clean_text(text)
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
            self.add_document(genre, doc)
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
        text = " ".join(forms)

        tokens = [t.lower() for t in forms]
        self.token_counts[genre] += len(tokens)
        self.term_freq.update(tokens)
        self.doc_freq.update(set(tokens))

        self.zip_file.writestr(filename, text)
        return filename

    def close(self) -> None:
        """Close the zip archive."""
        self.zip_file.close()

    def summary(self) -> dict[str, any]:
        """Return compilation summary metrics."""
        return {
            "total_documents": sum(self.doc_counts.values()),
            "total_tokens": sum(self.token_counts.values()),
            "unique_vocabulary": len(self.term_freq),
            "genre_docs": dict(self.doc_counts),
            "genre_tokens": dict(self.token_counts),
            "archive_size_bytes": self.output_zip_path.stat().st_size if self.output_zip_path.exists() else 0,
        }
