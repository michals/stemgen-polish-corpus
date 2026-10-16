# stemgen: Corpus-Driven Micro-Stemmer Compiler

> **Knowledge Distillation for BM25 Retrieval**: Compile heavy morphological analyzers (Stanza, spaCy, Morfeusz, local LLMs) and domain corpora into ultra-fast, zero-dependency micro-stemmers (<30 KB) emitting standalone **JavaScript (ESM)**, **Python**, and **Snowball DSL (`.sbl`)**.

[![Tests](https://img.shields.io/badge/pytest-passing-brightgreen.svg)](#6-development--verification)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)](#prerequisites)
[![Parity](https://img.shields.io/badge/parity-100%25%20bit--for--bit-success.svg)](#4-consuming-the-emitted-stemmers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Quickstart: The End-to-End Build Command

Compile a complete micro-stemmer from any raw corpus ZIP archive or directory with one command:

```bash
uv run stemgen build \
  --corpus data/domains/pl/bt5/corpus.zip \
  --profile md \
  --teacher stanza \
  --target js,py,sbl \
  --output-dir dist/
```

What `stemgen build` does automatically:
1. **Stage 1 (Ground Truth Extraction & Dual-Layer Caching)**: Reuses existing completed ground truth (Level-1 cache) or extracts document units with persistent SQLite caching (Level-2 `TeacherCache`), skipping neural model initialization on 100% cache hits.
2. **Stage 2 (Compilation)**: Induces canonical cluster targets, derives `CutAdd` operations, builds the reversed suffix-trie, and applies MDL cost-complexity pruning according to the `--profile` preset (`xs`, `sm`, `md`, `lg`, `xl`).
3. **Stage 3 (Evaluation & Benchmarking)**: Computes exact $O(|V|)$ BCubed precision/recall and prints a rich side-by-side terminal comparison against the official Snowball Polish reference baseline.
4. **Stage 4 (Multi-Target Codegen)**: Emits standalone, zero-dependency source files for **JavaScript (ESM)**, **Python**, and **Snowball DSL**.

---

## 2. Benchmark Results on the Polish Millennium Bible (`bt5`)

Evaluated on **60,435** unique words from the complete text of the Polish Millennium Bible (*Biblia Tysiąclecia*):

| Stemmer System | Target Bundle Size (Gzip) | BCubed Precision | BCubed Recall | Weighted $F_1$ | Pairwise $F_1$ | Throughput |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`bt5_stemmer_xl` (stemgen)** 🌟 | **61.9 KB** | **95.88%** | **92.44%** | **94.13%** | **84.00%** | **> 540,000 w/s** |
| **`bt5_stemmer_md` (stemgen)** | **60.2 KB** | **95.74%** | **91.57%** | **93.61%** | **83.17%** | **> 530,000 w/s** |
| **`bt5_stemmer_sm` (stemgen)** | **4.8 KB** | **91.84%** | **73.83%** | **81.86%** | **56.77%** | **> 650,000 w/s** |
| `stemmer-snowball.js` (Reference Baseline) | 12.5 KB | 70.09% | 83.75% | 76.32% | 51.49% | 221,000 w/s |
| `simple_stemmer` (Python 3) | N/A | 79.40% | 68.12% | 73.33% | 37.40% | 510,000 w/s |
| `pl_stemmer` (Tutanchamon) | N/A | 77.90% | 65.70% | 71.28% | 32.92% | 408,000 w/s |

> **Key Takeaway**: Even the compact **`sm` profile (4.8 KB gzipped)** beats the official Snowball Polish reference baseline by **+5.5% $F_1$** and **+21.7% Precision** at less than half the code size.

---

## 3. Architecture & Dual-Layer Caching

### Non-Destructive Run Hierarchy
`stemgen` saves all intermediate and completed artifacts in an isolated, convention-based hierarchy:
```
data/
├── cache/
│   └── teacher_cache.sqlite     # Level-2 document-level lemmatization cache (WAL mode, zlib compressed)
└── runs/
    └── <corpus_id>/             # e.g., bt5, general, custom
        └── <teacher_id>/        # e.g., stanza_pdb, spacy_pl_core_news_md
            ├── ground_truth.parquet  # Level-1 completed ground truth
            ├── summary.json          # Vocabulary and token mass statistics
            ├── models/               # Compiled model JSONs (xs, sm, md, lg, xl)
            ├── reports/              # Markdown comparative benchmark reports
            └── dist/                 # Emitted target code modules (.js, .py, .sbl)
```

### Dual-Layer Caching System
1. **Level-1 Cache (Run / Dataset Level)**: If `ground_truth.parquet` already exists in `data/runs/<corpus_id>/<teacher_id>/`, subsequent `stemgen build` runs reuse it instantly without scanning text or initializing lemmatizers. (Override with `--force`).
2. **Level-2 Cache (Document Level via SQLite `TeacherCache`)**: Document text hashes (`SHA-256`) and their `(word, lemma)` tuples are stored in SQLite with WAL mode. Overlapping genres, incremental corpus extensions, or re-runs across different configurations reuse previously analyzed documents instantly with zero neural inference overhead.

---

## 4. Compilation Profiles

| Profile | Trie Depth | $\lambda$ Penalty | Exceptions ($\text{Top-}K$) | Target Bundle Size | Intended Use Case |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`xs`** | 5 | 0.005 | 50 | < 10 KB (< 2 KB gz) | Ultra-compact micro-bundles, IoT, embedded |
| **`sm`** | 5 | 0.001 | 150 | < 25 KB (< 5 KB gz) | Compact client web apps (beats Snowball) |
| **`md`** | 7 | 0.0001 | 450 | < 40 KB (< 12 KB gz) | **Recommended default**: optimal balance ($F_1 > 0.93$) |
| **`lg`** | 8 | 0.00003 | 800 | < 100 KB (< 25 KB gz) | High-coverage analytics & search |
| **`xl`** | 9 | 0.00001 | 1,200 | < 200 KB (< 40 KB gz) | Maximum morphological fidelity ($F_1 > 0.96$) |

---

## 5. CLI Reference Manual

### Unified Workflow Command
```bash
# Build with default md profile
uv run stemgen build --corpus data/domains/pl/bt5/corpus.zip

# Build compact sm profile for edge deployment
uv run stemgen build --corpus data/domains/pl/bt5/corpus.zip --profile sm --target js,py

# Force re-extraction bypassing Level-1 cache
uv run stemgen build --corpus data/domains/pl/bt5/corpus.zip --force
```

### Modular Subcommands
For granular pipeline control and hyperparameter sweeps:

- **Extract Ground Truth (`build-ground-truth`)**:
  ```bash
  uv run stemgen build-ground-truth \
    --corpus data/domains/pl/bt5/corpus.zip \
    --output-dir data/runs/bt5/stanza_pdb/ \
    --teacher stanza --batch-size 512
  ```

- **Compile Model (`compile`)**:
  ```bash
  # Compile using profile preset and emit code immediately
  uv run stemgen compile \
    --ground-truth data/runs/bt5/stanza_pdb/ground_truth.parquet \
    --profile md \
    --output-dir data/models/ \
    --model-name bt5_md \
    --emit js,py,sbl \
    --eval
  ```

- **Evaluate Model vs Baselines (`evaluate-model`)**:
  ```bash
  uv run stemgen evaluate-model \
    --model data/models/bt5_md.json \
    --ground-truth data/runs/bt5/stanza_pdb/ground_truth.parquet \
    --reports-dir data/reports
  ```

- **Emit Standalone Code (`emit`)**:
  ```bash
  uv run stemgen emit \
    --model data/models/bt5_md.json \
    --target js,py,sbl \
    --output-dir dist/
  ```

- **Map Pareto Frontier (`sweep-pareto`)**:
  ```bash
  uv run stemgen sweep-pareto \
    --ground-truth data/runs/bt5/stanza_pdb/ground_truth.parquet \
    --reports-dir data/reports
  ```

---

## 6. Programmatic Python SDK

You can use `stemgen` directly as a Python library:

```python
import stemgen

# 1. Run complete compilation pipeline programmatically
result = stemgen.build_stemmer_pipeline(
    corpus_path="data/domains/pl/bt5/corpus.zip",
    profile="md",
    teacher="stanza",
    targets=["js", "py", "sbl"],
    output_dir="dist",
)

print(f"Model F1: {result['model_metrics']['f1']:.4f}")
print(f"Emitted artifacts: {result['emitted_files']}")

# 2. Or load and run a compiled model in memory
model = stemgen.CompiledStemmerModel.load("data/models/bt5_md.json")
assert model.stem("bogu") == "bog"
assert model.stem("chłopcami") == "chlopc"
```

---

## 7. Consuming Emitted Zero-Dependency Stemmers

The generated stemmers have **zero external runtime dependencies**.

### JavaScript / TypeScript (ES Module)
```javascript
import { stem } from './dist/stemmer_bt5_balanced.js';

console.log(stem('bogu'));      // "bog"
console.log(stem('widziałem')); // "widzie"
console.log(stem('synowie'));   // "syn"
```

### Python 3
```python
from dist.stemmer_bt5_balanced import stem

print(stem("bogu"))  # "bog"
print(stem("widziałem"))  # "widzie"
```

### Snowball DSL (`.sbl`)
Compatible with official Snowball compilers for C, Java (Lucene/Elasticsearch), Rust, and Go:
```bash
# Compile to C for PostgreSQL FTS or SQLite FTS5:
snowball dist/stemmer_bt5_balanced.sbl -o dist/stemmer -c -ep polish_

# Compile to Java for Apache Lucene / Elasticsearch:
snowball dist/stemmer_bt5_balanced.sbl -o dist/Stemmer -j -p org.apache.lucene.analysis.pl
```

---

## 8. Development & Verification

```bash
# Run test suite
uv run pytest

# Check code formatting & types
uv run ruff check .
uv run ruff format --check .
```

---

## License
MIT
