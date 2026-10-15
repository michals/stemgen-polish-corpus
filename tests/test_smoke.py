import pytest

from polish_corpus.builder import build_polish_corpus
from polish_corpus.cli import main
from polish_corpus.config import TIERS, TierConfig


def test_package_exports() -> None:
    """Verify package configuration and tiers are exposed."""
    assert "recommended" in TIERS
    assert "compact" in TIERS
    assert "extended" in TIERS
    assert isinstance(TIERS["recommended"], TierConfig)


def test_default_tier_subdir() -> None:
    """Verify default output directory nests by tier name."""
    from polish_corpus.config import get_default_output_dir
    p = get_default_output_dir("recommended")
    assert p.name == "recommended"
    assert p.parent.name == "dist"


def test_quick_test_run(tmp_path) -> None:
    """Verify quick test pipeline runs end-to-end and creates expected artifacts."""
    pytest.importorskip("pyarrow", reason="pyarrow required for parquet export")
    out_dir = tmp_path / "output"
    exit_code = build_polish_corpus(
        tier_name="recommended",
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
