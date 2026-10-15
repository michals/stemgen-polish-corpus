"""Multi-genre balanced Polish corpus generator and gold morphological ground truth compiler."""

from .builder import build_polish_corpus
from .config import DEFAULT_OUTPUT_BASE, TIERS, TierConfig, get_default_output_dir

__version__ = "0.1.0"
__all__ = [
    "__version__",
    "build_polish_corpus",
    "TIERS",
    "TierConfig",
    "DEFAULT_OUTPUT_BASE",
    "get_default_output_dir",
]
