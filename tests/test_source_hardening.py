"""Regression tests for Phase 2 tracer guards: dedup seen-set and URL/email strip."""

from __future__ import annotations

import pytest

import polish_corpus.text_sources as text_sources
from polish_corpus.corpus_sampler import chunk_text_stream
from polish_corpus.text_cleaning import clean_text, tokenize
from polish_corpus.text_sources import (
    _is_boilerplate,
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


@pytest.mark.parametrize(
    "line",
    [
        "Ten utwór nie jest objęty prawem autorskim",
        "ISBN 978-83-123456-7-8 udostępniony przez wydawcę",
        "Tekst opracowany przez Wolne Lektury",
        "Udostępnione przez Fundację Nowoczesna Polska",
        "Czytaj dalej na stronie biblioteki internetowej",
        "Pobierz ebook w formacie PDF na czytnik",
        "ROZDZIAŁ III",
        "Rozdział 7",
        "CZĘŚĆ II",
        "Tom II",
        "Księga II",
        "XVII",
        "27",
        "***",
        "===",
        "*** KONIEC ***",
        "Przypis: zobacz objaśnienia wydawcy na końcu tomu",
        "Uwaga edytora: pisownia uwspółcześniona",
    ],
)
def test_boilerplate_lines_drop(line: str) -> None:
    """Verify WL export boilerplate lines are classified as boilerplate."""
    assert _is_boilerplate(line) is True


@pytest.mark.parametrize(
    "line",
    [
        "W trzecim rozdziale bohater postanowił opuścić rodzinne miasto o świcie",
        "Janusz stał pod arkadami kamienicy, wpatrując się w ciemną toń rzeki",
        "Rozdział ten zapamiętał na długo, bo opowiadał o dawnych dziejach miasta",
        "Siedemnasty dzień podróży minął im spokojnie wśród zielonych wzgórz",
    ],
)
def test_prose_with_boilerplate_words_retained(line: str) -> None:
    """Verify mid-sentence prose mentioning rozdział survives the filter."""
    assert _is_boilerplate(line) is False


def test_is_boilerplate_never_raises() -> None:
    """Verify the helper is lenient on weird input."""
    assert _is_boilerplate("") is False
    assert _is_boilerplate("   ") is False
    assert _is_boilerplate("x" * 500) is False
