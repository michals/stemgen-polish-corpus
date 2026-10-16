import zipfile

import pytest

from polish_corpus.corpus_sampler import BalancedCorpusWriter, chunk_text_stream
from polish_corpus.text_cleaning import clean_text, is_valid_token, tokenize


@pytest.mark.parametrize(
    "dirty",
    [
        "Béziera",
        "café",
        "COVID-19",
    ],
)
def test_foreign_tokens_drop_whole(dirty: str) -> None:
    """Verify foreign/numeric tokens vanish entirely, leaving no fragments."""
    cleaned = clean_text(f"słowo {dirty} inne")
    leftovers = tokenize(cleaned)
    assert dirty not in leftovers
    for fragment in ("ziera", "caf", "COVID"):
        assert fragment not in leftovers
        assert fragment not in cleaned
    # Surrounding Polish signal is preserved.
    assert "słowo" in leftovers
    assert "inne" in leftovers


def test_hyphenated_polish_compound_retained() -> None:
    """Verify biało-czerwony survives cleaning and tokenization."""
    assert clean_text("biało-czerwony") == "biało-czerwony"
    assert tokenize("flaga biało-czerwony powiewa") == ["flaga", "biało-czerwony", "powiewa"]


def test_multi_hyphen_compound_retained_whole() -> None:
    """Verify triple compounds tokenize whole, agreeing with is_valid_token."""
    assert is_valid_token("biało-czerwono-zielony")
    assert tokenize("x biało-czerwono-zielony y") == ["x", "biało-czerwono-zielony", "y"]


def test_stored_text_and_counts_agree(tmp_path) -> None:
    """Verify re-tokenizing stored zip text reproduces recorded TF/DF."""
    writer = BalancedCorpusWriter(tmp_path / "corpus.zip")
    writer.add_document(
        "04_wikipedia",
        "Béziera przyjechała do café na COVID-19 oraz biało-czerwony sztandar",
    )
    writer.close()

    with zipfile.ZipFile(tmp_path / "corpus.zip") as archive:
        stored = archive.read("04_wikipedia/doc_00001.txt").decode("utf-8")

    assert "ziera" not in stored
    assert "caf" not in stored
    assert "COVID" not in stored
    assert "biało-czerwony" in stored

    retokenized = [t.lower() for t in tokenize(stored)]
    assert sorted(retokenized) == sorted(writer.term_freq.elements())
    assert set(retokenized) == set(writer.doc_freq)


def test_entity_decodes_before_filter() -> None:
    """Verify &eacute; decodes to é and is then dropped, never passed through."""
    cleaned = clean_text("słowo &eacute; inne")
    assert "&eacute;" not in cleaned
    assert "eacute" not in tokenize(cleaned)
    leftovers = tokenize(cleaned)
    assert "słowo" in leftovers
    assert "inne" in leftovers
    # The decoded é-token leaves no countable fragment behind.
    assert not any(t == "e" for t in leftovers if t not in ("słowo", "inne"))


def test_nfd_foreign_input_drops_after_nfc() -> None:
    """Verify NFD e + combining acute composes to é under NFC, then drops."""
    nfd_cafe = "cafe\u0301"
    assert nfd_cafe != "café"  # guard: fixture really is decomposed
    cleaned = clean_text(f"słowo {nfd_cafe} inne")
    leftovers = tokenize(cleaned)
    assert "caf" not in leftovers
    assert "caf" not in cleaned
    assert "słowo" in leftovers
    assert "inne" in leftovers


def test_control_and_fffd_stripped() -> None:
    """Verify control characters and U+FFFD vanish while newlines survive."""
    cleaned = clean_text("słowo\x00\x01\x07 inne\ufffd dalsze")
    assert "\x00" not in cleaned
    assert "\ufffd" not in cleaned
    assert tokenize(cleaned) == ["słowo", "inne", "dalsze"]
    with_newline = clean_text("pierwszy akapit\n\ndrugi akapit")
    assert "\n" in with_newline


def test_entity_encoded_combining_mark_drops_whole() -> None:
    """Verify cafe&#769; (entity-encoded combining acute) vanishes whole."""
    cleaned = clean_text("słowo cafe&#769; inne")
    assert "cafe" not in tokenize(cleaned)
    assert "cafe" not in cleaned
    assert tokenize(cleaned) == ["słowo", "inne"]


def test_non_composable_decomposed_sequence_drops_whole() -> None:
    """Verify a combining mark with no NFC precomposition drops the token."""
    # q + U+0301 + x: NFC has no precomposition for q + acute, so the
    # combining mark survives to the token filter, which must drop it.
    decomposed = "q" + chr(0x301) + "x"
    assert decomposed != "qx"  # guard: fixture really carries a mark
    cleaned = clean_text(f"słowo {decomposed} inne")
    assert tokenize(cleaned) == ["słowo", "inne"]


@pytest.mark.parametrize("encoded", ["słowo &#0; inne", "słowo &#xFFFD; inne"])
def test_encoded_stripped_chars_stay_stripped(encoded: str) -> None:
    """Verify char refs of stripped chars decode then face the strip."""
    assert clean_text(encoded) == "słowo inne"


def test_quote_dash_normalization_without_resurrection() -> None:
    """Verify quote/dash variants normalize and never launder dropped tokens."""
    assert clean_text("„cytat”") == '"cytat"'
    assert clean_text("«cytat»") == '"cytat"'
    assert clean_text("słowo — inne") == "słowo - inne"
    assert clean_text("słowo – inne") == "słowo - inne"
    # Filter runs before punctuation normalization: no COVID-19 -> COVID salvage.
    cleaned = clean_text("model COVID-19 test")
    assert "COVID" not in tokenize(cleaned)
    assert "COVID" not in cleaned
    assert tokenize(cleaned) == ["model", "test"]


@pytest.mark.parametrize(
    "adversarial",
    [
        "",
        "   ",
        "\x00\x01\x02\ufffd",
        "&eacute;&eacute;&eacute;",
        "cafe\u0301",
        "COVID-19 2012 model3 Béziera Hübner",
        "„«»\"\"——–",
        "\n\n\n",
        "a\tb",
    ],
)
def test_clean_text_never_raises(adversarial: str) -> None:
    """Verify clean_text returns a string on adversarial input without raising."""
    result = clean_text(adversarial)
    assert isinstance(result, str)


@pytest.mark.parametrize(
    "dirty",
    [
        "Schrödinger",
        "Besançon",
        "Turčianske",
        "Corrèze",
        "Hübner",
        "Maréchal",
        "désintéressement",
        "Führer",
        "naïve",
        "Linköping",
        "Saint-Étienne-la-Geneste",
    ],
)
def test_audit_drop_fixtures_vanish_whole(dirty: str) -> None:
    """Verify every audit §2 drop-case vanishes whole with no salvage."""
    cleaned = clean_text(f"słowo {dirty} inne")
    leftovers = tokenize(cleaned)
    assert leftovers == ["słowo", "inne"]
    # No letter-part salvage: fragments must not survive in text or tokens.
    for fragment in ("H", "bner", "tienne-la", "Geneste", "Saint"):
        assert fragment not in leftovers
        assert fragment not in cleaned


@pytest.mark.parametrize("dirty", ["2012", "model3", "COVID-19"])
def test_numeric_tokens_excluded_from_counts(dirty: str) -> None:
    """Verify numeric/alphanumeric tokens are excluded via both gates."""
    assert not is_valid_token(dirty)
    assert clean_text(dirty) == ""
    assert dirty not in tokenize(f"słowo {dirty} inne")


@pytest.mark.parametrize(
    "word",
    ["Ala", "chrząszcz", "źdźbło", "biało-czerwony"],
)
def test_valid_polish_retained(word: str) -> None:
    """Verify sentence-initial capitals and Polish words survive both gates."""
    assert is_valid_token(word)
    assert word in tokenize(f"{word} inne")


def test_hyphen_per_segment_validation() -> None:
    """Verify each hyphen segment must be non-empty and Polish-only."""
    assert is_valid_token("biało-czerwony")
    assert not is_valid_token("Saint-Étienne")
    assert not is_valid_token("biało-")
    assert not is_valid_token("-czerwony")
    # Whole-token drop at clean stage: no tienne-la salvage from the compound.
    cleaned = clean_text("w Saint-Étienne-la-Geneste mieście")
    assert "tienne" not in cleaned
    assert tokenize(cleaned) == ["w", "mieście"]


def test_chunker_skips_foreign_only_paragraph() -> None:
    """Verify paragraphs with no countable Polish tokens never form docs."""
    docs = list(
        chunk_text_stream(iter(["Béziera café", "Ala ma kota i psa"]), target_words=5, min_words=1)
    )
    assert docs == ["Ala ma kota i psa"]


def test_empty_after_clean_flows_through(tmp_path) -> None:
    """Verify text that cleans to empty never breaks the pipeline."""
    assert clean_text("COVID-19 2012 Béziera") == ""
    # Zero-count paragraphs take the existing chunk_text_stream skip-empty path.
    docs = list(chunk_text_stream(iter(["2012 !!!", "Ala ma kota i psa"]), target_words=5, min_words=1))
    assert docs == ["Ala ma kota i psa"]
    # A doc that cleans to empty still flows through the writer gate cleanly.
    writer = BalancedCorpusWriter(tmp_path / "corpus.zip")
    writer.add_document("04_wikipedia", "COVID-19 2012 Béziera")
    writer.close()
    assert dict(writer.term_freq) == {}
    assert dict(writer.doc_freq) == {}
    with zipfile.ZipFile(tmp_path / "corpus.zip") as archive:
        stored = archive.read("04_wikipedia/doc_00001.txt").decode("utf-8")
    assert stored == ""
