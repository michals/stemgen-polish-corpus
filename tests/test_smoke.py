import pytest

from polish_corpus.builder import build_polish_corpus
from polish_corpus.cli import main
from polish_corpus.config import TIERS, TierConfig


def test_package_exports() -> None:
    """Verify package configuration and tiers are exposed."""
    assert "md" in TIERS
    assert "sm" in TIERS
    assert "lg" in TIERS
    assert isinstance(TIERS["md"], TierConfig)


def test_default_tier_subdir() -> None:
    """Verify default output directory nests by tier name."""
    from polish_corpus.config import get_default_output_dir
    p = get_default_output_dir("md")
    assert p.name == "md"
    assert p.parent.name == "dist"


def test_quick_test_run(tmp_path) -> None:
    """Verify quick test pipeline runs end-to-end and creates expected artifacts."""
    pytest.importorskip("pyarrow", reason="pyarrow required for parquet export")
    out_dir = tmp_path / "output"
    exit_code = build_polish_corpus(
        tier_name="md",
        output_dir=out_dir,
        quick_test=True,
    )
    assert exit_code == 0
    assert (out_dir / "corpus.zip").exists()
    assert (out_dir / "ground_truth.parquet").exists()
    assert (out_dir / "ground_truth_train.parquet").exists()
    assert (out_dir / "ground_truth_test.parquet").exists()
    assert (out_dir / "snowball_voc_ground_truth.parquet").exists()
    assert (out_dir / "build_summary.json").exists()


def test_cli_help(capsys) -> None:
    """Verify CLI help output."""
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert "stemgen-polish-corpus" in captured.out
    assert "--tier" in captured.out
