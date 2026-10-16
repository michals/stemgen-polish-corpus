"""Regression tests for Phase 2 tracer guards: dedup seen-set and URL/email strip."""

from __future__ import annotations

import pytest

import polish_corpus.text_sources as text_sources
from polish_corpus.corpus_sampler import chunk_text_stream
from polish_corpus.text_cleaning import clean_text, tokenize
from polish_corpus.text_sources import (
    iter_literature_docs,
    iter_news_docs,
    iter_spoken_forum_docs,
    iter_wikipedia_docs,
)


def _collect_with_stubbed_chunks(iterator_fn, docs: list[str], max_docs: int) -> list[str]:
    """Run an iter_*_docs with chunk_text_stream stubbed to a finite doc supply."""
    original = text_sources.chunk_text_stream

    def _stub(paragraphs, target_words: int = 500, min_words: int = 200):  # noqa: ANN001, ANN202
        yield from docs

    text_sources.chunk_text_stream = _stub
    try:
        return list(iterator_fn(max_docs))
    finally:
        text_sources.chunk_text_stream = original


_STUB_DOCS = [
    "Ala ma kota i psa oraz kanarka w domu",
    "Kot pije mleko codziennie rano i wieczorem",
]


@pytest.mark.parametrize(
    "iterator_fn",
    [iter_spoken_forum_docs, iter_literature_docs, iter_news_docs, iter_wikipedia_docs],
)
def test_short_source_yields_each_doc_exactly_once(iterator_fn) -> None:
    """Verify a 2-doc source asked for 5 docs yields exactly 2 distinct docs."""
    assert _collect_with_stubbed_chunks(iterator_fn, _STUB_DOCS, max_docs=5) == _STUB_DOCS


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/x",
        "http://example.com/foo",
        "www.example.com/strona",
    ],
)
def test_url_stripped_whole_with_polish_retained(url: str) -> None:
    """Verify URLs vanish whole while surrounding Polish survives."""
    cleaned = clean_text(f"kot {url} pije")
    assert tokenize(cleaned) == ["kot", "pije"]
    for fragment in ("http", "example", "com", "www"):
        assert fragment not in cleaned


def test_url_only_paragraph_cleans_empty_and_skips_chunker() -> None:
    """Verify a URL-only paragraph takes the chunk_text_stream skip-empty path."""
    assert clean_text("https://example.com/x") == ""
    docs = list(
        chunk_text_stream(
            iter(["https://example.com/x", "Ala ma kota i psa"]),
            target_words=5,
            min_words=1,
        )
    )
    assert docs == ["Ala ma kota i psa"]


def test_email_stripped_whole_with_surroundings_retained() -> None:
    """Verify jan@domena.pl drops whole with surrounding Polish retained."""
    cleaned = clean_text("napisz na adres jan@domena.pl proszę")
    assert tokenize(cleaned) == ["napisz", "na", "adres", "proszę"]
    assert "jan" not in cleaned
    assert "domena" not in cleaned


@pytest.mark.parametrize(
    ("dirty", "dropped"),
    [
        ("café", True),
        ("biało-czerwony", False),
    ],
)
def test_phase1_spot_checks_hold_after_url_strip(dirty: str, dropped: bool) -> None:
    """Verify Phase 1 behavior is unchanged by the new URL/email step."""
    cleaned = clean_text(f"słowo {dirty} inne")
    if dropped:
        assert tokenize(cleaned) == ["słowo", "inne"]
    else:
        assert tokenize(cleaned) == ["słowo", dirty, "inne"]
