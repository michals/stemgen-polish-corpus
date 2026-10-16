"""Regression tests for Phase 3 tracer: input-honest audit rates end-to-end."""

from __future__ import annotations

import pytest

from polish_corpus.corpus_sampler import BalancedCorpusWriter, chunk_text_stream
from polish_corpus.text_cleaning import AuditCounts, audit_clean, clean_text, tokenize


def test_audit_rates_exact_arithmetic(tmp_path) -> None:
    """Verify exact counters and rates on a paragraph of known composition."""
    writer = BalancedCorpusWriter(tmp_path / "corpus.zip")
    genre = "03_nkjp_news"
    dirty = "kot pies dom stół chmura drzewo rzeka góra café naïve model3 https://example.com/x"
    assert writer.add_document(genre, dirty) != ""

    _, counts = audit_clean(dirty)
    assert counts == AuditCounts(
        foreign_dropped=2,
        digit_dropped=1,
        url_removed=1,
        email_removed=0,
        tokens_kept=8,
    )

    rates = writer.summary()["audit_rates"]
    entry = rates["per_genre"][genre]
    assert entry["foreign_dropped"] == 2
    assert entry["digit_dropped"] == 1
    assert entry["url_removed"] == 1
    assert entry["email_removed"] == 0
    assert entry["tokens_kept"] == 8
    assert entry["dropped_total"] == 3
    assert entry["foreign_fragment_rate"] == 2 / 11
    assert entry["digit_token_rate"] == 1 / 11
    assert rates["global"]["foreign_dropped"] == 2
    assert rates["global"]["digit_token_rate"] == 1 / 11
    assert rates["paradigm_docs_excluded"] is True
    writer.close()


def test_sizing_path_does_not_double_count(tmp_path) -> None:
    """Verify chunk_text_stream cleaning leaves writer counters untouched."""
    writer = BalancedCorpusWriter(tmp_path / "corpus.zip")
    genre = "03_nkjp_news"
    dirty_paras = [
        "kot pies dom café",
        "model3 chmura drzewo",
        "rzeka góra naïve https://example.com/x",
    ]
    _, raw = audit_clean(" ".join(dirty_paras))
    assert raw.foreign_dropped + raw.digit_dropped > 0

    docs = list(chunk_text_stream(iter(dirty_paras), target_words=4, min_words=1))
    assert docs, "chunker should emit docs from dirty input"
    assert all(v == 0 for counts in writer.audit_counts.values() for v in counts.values())

    for doc in docs:
        writer.add_document(genre, doc)
    entry = writer.summary()["audit_rates"]["per_genre"][genre]
    assert entry["foreign_dropped"] == 0
    assert entry["digit_dropped"] == 0
    assert entry["tokens_kept"] == sum(len(tokenize(doc)) for doc in docs)
    writer.close()


def test_empty_after_clean_records_drops_without_quota(tmp_path) -> None:
    """Verify a fully-dropped doc records drops but consumes no quota."""
    writer = BalancedCorpusWriter(tmp_path / "corpus.zip")
    genre = "03_nkjp_news"
    assert writer.add_document(genre, "café 123 https://example.com/x") == ""
    assert writer.doc_counts[genre] == 0

    entry = writer.summary()["audit_rates"]["per_genre"][genre]
    assert entry["foreign_dropped"] == 1
    assert entry["digit_dropped"] == 1
    assert entry["url_removed"] == 1
    assert entry["tokens_kept"] == 0
    assert entry["foreign_fragment_rate"] == 1 / 2
    assert entry["digit_token_rate"] == 1 / 2
    writer.close()


@pytest.mark.parametrize(
    "dirty",
    [
        "kot café pije",
        "model3 i COVID-19",
        "napisz na adres jan@domena.pl proszę",
        "zobacz https://example.com/x oraz www.example.com/strona",
        "Béziera naïve Saint-Étienne-la-Geneste",
        "„Cześć” — powiedział",
        "",
        "   ",
        "Ala ma kota i psa",
    ],
)
def test_clean_text_delegates_to_audit_clean(dirty: str) -> None:
    """Verify clean_text output is identical to the audit_clean text channel."""
    assert audit_clean(dirty)[0] == clean_text(dirty)
