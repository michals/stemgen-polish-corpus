"""Regression tests for Phase 3 tracer: input-honest audit rates end-to-end."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

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


# Audit-trace consolidation (quality-audit.md §2, all 14 rows).
#
# Existing batteries already pin most rows at clean_text() level — referenced
# here, not duplicated:
#   - Béziera / café / COVID-19 → test_cleaning.py::test_foreign_tokens_drop_whole
#   - Schrödinger, Besançon, Turčianske, Corrèze, Hübner, Maréchal,
#     désintéressement, Führer, naïve, Linköping,
#     Saint-Étienne-la-Geneste → test_cleaning.py::test_audit_drop_fixtures_vanish_whole
# What this table adds per RESEARCH §2: (1) an explicit audit-row case ID per
# row so completeness is mechanically checkable; (2) no-salvage pins naming
# the historic TOKEN_RE fragments from the audit table, asserted at the
# correct level — non-generation via tokenize(clean_text(dirty)), never
# is_valid_token() on Polish-class fragments (e.g. is_valid_token("ziera")
# is correctly True; the guarantee is that "ziera" is never generated);
# (3) gap-fill variants absent from test_cleaning.py (Turčianske Teplice,
# Mein Führer, Anthé).
@pytest.mark.parametrize(
    ("dirty", "expected", "forbidden"),
    [
        pytest.param("Béziera", ["słowo", "inne"], ("B", "ziera", "Béziera"), id="audit-Beziera"),
        pytest.param(
            "Besançon", ["słowo", "inne"], ("Besan", "on", "Besançon"), id="audit-Besancon"
        ),
        pytest.param(
            "Turčianske", ["słowo", "inne"], ("Tur", "ianske", "Turčianske"), id="audit-Turcianske"
        ),
        pytest.param(
            "Saint-Étienne-la-Geneste",
            ["słowo", "inne"],
            ("Saint", "tienne-la", "tienne", "Geneste", "Étienne"),
            id="audit-Saint-Etienne-la-Geneste",
        ),
        pytest.param("Corrèze", ["słowo", "inne"], ("Corr", "ze", "Corrèze"), id="audit-Correze"),
        pytest.param(
            "Schrödinger",
            ["słowo", "inne"],
            ("Schr", "dinger", "Schrödinger"),
            id="audit-Schrodinger",
        ),
        pytest.param("Hübner", ["słowo", "inne"], ("H", "bner", "Hübner"), id="audit-Hubner"),
        pytest.param(
            "Maréchal", ["słowo", "inne"], ("Mar", "chal", "Maréchal"), id="audit-Marechal"
        ),
        pytest.param(
            "désintéressement",
            ["słowo", "inne"],
            ("d", "sint", "ressement", "désintéressement"),
            id="audit-desinteressement",
        ),
        pytest.param("Führer", ["słowo", "inne"], ("F", "hrer", "Führer"), id="audit-Fuhrer"),
        pytest.param("café", ["słowo", "inne"], ("caf", "café"), id="audit-cafe"),
        pytest.param("naïve", ["słowo", "inne"], ("na", "ve", "naïve"), id="audit-naive"),
        pytest.param("COVID-19", ["słowo", "inne"], ("COVID", "COVID-19"), id="audit-COVID-19"),
        pytest.param(
            "Linköping", ["słowo", "inne"], ("Link", "ping", "Linköping"), id="audit-Linkoping"
        ),
        # Gap-fill variants (§3 source evidence, not in test_cleaning.py).
        pytest.param(
            "Turčianske Teplice",
            ["słowo", "Teplice", "inne"],
            ("Tur", "ianske", "Turčianske"),
            id="audit-variant-Turcianske-Teplice",
        ),
        pytest.param(
            "Mein Führer",
            ["słowo", "Mein", "inne"],
            ("F", "hrer", "Führer"),
            id="audit-variant-Mein-Fuhrer",
        ),
        pytest.param("Anthé", ["słowo", "inne"], ("Anth", "Anthé"), id="audit-variant-Anthe"),
    ],
)
def test_audit_row_leaves_no_salvage(
    dirty: str, expected: list[str], forbidden: tuple[str, ...]
) -> None:
    """Verify each audit §2 row drops whole with none of its historic fragments generated."""
    cleaned = clean_text(f"słowo {dirty} inne")
    leftovers = tokenize(cleaned)
    assert leftovers == expected
    for fragment in forbidden:
        # Exact-token absence: the fragment was never generated as a token.
        assert fragment not in leftovers
        # Substring absence for longer fragments: no salvage hides inside text.
        # (Skipped for 1-2 char fragments like "H"/"on"/"ze"/"na"/"ve", where
        # substring matching would be noise — exact-token absence pins those.)
        if len(fragment) >= 3:
            assert fragment not in cleaned


def _load_gate_script():
    """Import scripts/verify_zero_fragments.py without argparse side effects."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "verify_zero_fragments.py"
    spec = importlib.util.spec_from_file_location("verify_zero_fragments", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_zero_fragments"] = module
    spec.loader.exec_module(module)
    return module


def _write_synthetic_dist_dir(dist_dir: Path, *, dirty: bool) -> None:
    """Build a minimal dist dir: raw zip + matching GT parquet + summary rates."""
    genre = "04_wikipedia"
    doc_text = "Ala ma kota" if not dirty else "Ala ma kota Béziera"
    with zipfile.ZipFile(dist_dir / "corpus.zip", mode="w") as archive:
        archive.writestr(f"{genre}/doc_00001.txt", doc_text)
    words = [t.lower() for t in tokenize(doc_text)]
    gt_words = words if not dirty else [*words, "béziera"]
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_arrays(
        [
            pa.array(gt_words, type=pa.string()),
            pa.array([f"lemma{i}" for i in range(len(gt_words))], type=pa.string()),
            pa.array([1] * len(gt_words), type=pa.int64()),
            pa.array([1] * len(gt_words), type=pa.int64()),
        ],
        names=["word", "lemma", "tf", "df"],
    )
    pq.write_table(table, dist_dir / "ground_truth.parquet", compression="zstd")
    kept = len(tokenize("Ala ma kota"))
    (dist_dir / "build_summary.json").write_text(
        json.dumps(
            {
                "tier": "synthetic",
                "summary": {},
                "audit_rates": {
                    "global": {
                        "foreign_fragment_rate": 0.0,
                        "digit_token_rate": 0.0,
                        "dropped_total": 0,
                        "foreign_dropped": 0,
                        "digit_dropped": 0,
                        "tokens_kept": kept,
                        "url_removed": 0,
                        "email_removed": 0,
                    },
                    "per_genre": {},
                    "paradigm_docs_excluded": True,
                },
            }
        ),
        encoding="utf-8",
    )


def test_gate_flags_synthetic_dirty_corpus(tmp_path) -> None:
    """Verify the gate fails (nonzero exit) on a dirty synthetic build."""
    gate = _load_gate_script()
    _write_synthetic_dist_dir(tmp_path, dirty=True)
    report = gate.check_dist_dir(tmp_path)
    assert not report.passed
    assert report.doc_violations > 0
    assert gate.main(["--dist-dir", str(tmp_path)]) == 1


def test_gate_passes_synthetic_clean_corpus(tmp_path) -> None:
    """Verify the gate passes (zero exit) on a clean synthetic build."""
    gate = _load_gate_script()
    _write_synthetic_dist_dir(tmp_path, dirty=False)
    report = gate.check_dist_dir(tmp_path)
    assert report.passed
    assert report.cross_checks["stored_counts_agree"]
    assert report.cross_checks["tokens_kept_agree"]
    assert report.cross_checks["rate_arithmetic_ok"]
    assert report.cross_checks["unique_natural_docs"]
    assert report.cross_checks["zipf_top_words_sanity"]
    assert report.cross_checks["lemma_clustering_diversity"]
    assert report.cross_checks["canary_lemma_probes"]
    assert gate.main(["--dist-dir", str(tmp_path)]) == 0


def test_gate_flags_canary_violation_x8(tmp_path) -> None:
    """Verify X8 flags morphological canary regressions."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    gate = _load_gate_script()
    _write_synthetic_dist_dir(tmp_path, dirty=False)

    # Overwrite GT with a canary word pointing to wrong lemma (e.g. mają -> 'maja')
    table = pa.Table.from_arrays(
        [
            pa.array(["mają"], type=pa.string()),
            pa.array(["maja"], type=pa.string()),  # Wrong! Expected 'mieć'
            pa.array([1], type=pa.int64()),
            pa.array([1], type=pa.int64()),
        ],
        names=["word", "lemma", "tf", "df"],
    )
    pq.write_table(table, tmp_path / "ground_truth.parquet", compression="zstd")

    report = gate.check_dist_dir(tmp_path)
    assert not report.cross_checks["canary_lemma_probes"]
    assert not report.passed
    assert any("mają -> 'maja'" in v for v in report.telemetry["canary_violations"])


def test_gate_flags_duplicate_docs_x5(tmp_path) -> None:
    """Verify X5 flags repeated duplicate documents."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    gate = _load_gate_script()
    genre = "04_wikipedia"
    doc_text = ("Ala ma kota. " * 100).strip()  # 300 words
    # Write 60 identical documents
    with zipfile.ZipFile(tmp_path / "corpus.zip", mode="w") as archive:
        for i in range(60):
            archive.writestr(f"{genre}/doc_{i:05d}.txt", doc_text)

    words = [t.lower() for t in tokenize(doc_text)]
    from collections import Counter
    counts = Counter(words * 60)
    w_list = list(counts.keys())
    tf_list = [counts[w] for w in w_list]

    table = pa.Table.from_arrays(
        [
            pa.array(w_list, type=pa.string()),
            pa.array([f"lem_{w}" for w in w_list], type=pa.string()),
            pa.array(tf_list, type=pa.int64()),
            pa.array([60] * len(w_list), type=pa.int64()),
        ],
        names=["word", "lemma", "tf", "df"],
    )
    pq.write_table(table, tmp_path / "ground_truth.parquet", compression="zstd")
    kept = sum(tf_list)
    (tmp_path / "build_summary.json").write_text(
        json.dumps(
            {
                "tier": "synthetic",
                "audit_rates": {
                    "global": {
                        "foreign_fragment_rate": 0.0,
                        "digit_token_rate": 0.0,
                        "dropped_total": 0,
                        "foreign_dropped": 0,
                        "digit_dropped": 0,
                        "tokens_kept": kept,
                    },
                    "per_genre": {},
                },
            }
        ),
        encoding="utf-8",
    )

    report = gate.check_dist_dir(tmp_path)
    assert not report.cross_checks["unique_natural_docs"]
    assert not report.passed
    assert report.telemetry["unique_doc_ratio"] < 0.1

