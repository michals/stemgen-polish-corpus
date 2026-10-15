"""Command-line interface for Polish Corpus Builder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .builder import build_polish_corpus
from .config import TIERS


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="stemgen-polish-corpus",
        description="Multi-genre balanced Polish corpus generator and gold morphological ground truth compiler",
    )
    parser.add_argument(
        "--tier",
        choices=list(TIERS.keys()),
        default="recommended",
        help="Corpus size tier: compact (~2.4M tokens), recommended (~5.5M tokens), extended (~13.4M tokens)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Target output directory (default: ./dist/<tier>)",
    )
    parser.add_argument(
        "--polimorf-path",
        type=Path,
        default=None,
        help="Optional local path to polimorf-*.tab.gz",
    )
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Run fast smoke-test with internal seed data (takes < 0.2s)",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-downloading source datasets even if cached",
    )

    args = parser.parse_args(argv)

    return build_polish_corpus(
        tier_name=args.tier,
        output_dir=args.output_dir,
        polimorf_path=args.polimorf_path,
        quick_test=args.quick_test,
        force_download=args.force_download,
    )


if __name__ == "__main__":
    sys.exit(main())
