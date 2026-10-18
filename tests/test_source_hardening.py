"""Regression tests for Phase 2 tracer guards: dedup seen-set and URL/email strip."""

from __future__ import annotations

import zipfile

import pytest

import polish_corpus.text_sources as text_sources
from polish_corpus.corpus_sampler import BalancedCorpusWriter, chunk_text_stream
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


def test_add_paradigm_batch_punctuates_chunks(tmp_path) -> None:
    """Verify add_paradigm_batch groups forms in punctuated chunks ending with periods."""
    zip_path = tmp_path / "test_corpus.zip"
    writer = BalancedCorpusWriter(zip_path)

    forms = [f"forma{chr(97 + i)}" for i in range(25)]
    writer.add_paradigm_batch(1, forms)
    writer.close()

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path, "r") as zf:
        content = zf.read("99_morfeusz_paradigms/paradigm_0001.txt").decode("utf-8")
        lines = content.strip().split("\n")
        # 25 items with chunk_size 15 -> 2 lines: 15, 10
        assert len(lines) == 2
        for line in lines:
            assert line.endswith(".")
        # Verify tokens extracted match forms exactly
        extracted = tokenize(content)
        assert extracted == [f.lower() for f in forms]
    assert writer.term_freq["formaa"] == 1
    assert writer.doc_freq["formaa"] == 1


def test_literature_docs_stops_at_footer(tmp_path, monkeypatch) -> None:
    """Verify iter_literature_docs stops reading a book when '-----' is encountered."""
    lit_dir = tmp_path / "literature"
    lit_dir.mkdir()
    book_file = lit_dir / "test_book.txt"
    # Provide >250 words before footer delimiter so chunker forms a full document
    prose_before = (
        "To jest piękna polska opowieść o dawnych czasach rycerzy i królów na wawelskim zamku. " * 35
    )
    footer_text = (
        "Ta lektura dostępna jest na licencji Creative Commons i w domenie publicznej. " * 20
    )
    book_file.write_text(
        f"{prose_before}\n-----\n{footer_text}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(text_sources, "CACHE_DIR", tmp_path)

    docs = list(iter_literature_docs(max_docs=10))
    assert len(docs) >= 1
    joined_docs = " ".join(docs)
    assert "polska opowieść" in joined_docs
    assert "Creative Commons" not in joined_docs
    assert "domenie publicznej" not in joined_docs
