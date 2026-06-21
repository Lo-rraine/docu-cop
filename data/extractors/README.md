# Corpus Extractors

Reusable tools for converting mirrored websites and other sources into clean Markdown corpora suitable for semantic search and embedding.

Managed with [`uv`](https://github.com/astral-sh/uv) for fast, isolated Python environment management.

## Setup

Install dependencies and create the virtual environment:

```bash
cd data/extractors
uv sync
```

With development dependencies:

```bash
uv sync --all-extras
```

## Scripts

### `convert_mirror.py` — Website Mirror to Markdown

Converts a wget-mirrored website into a deduplicated Markdown corpus.

**Features:**
- Recursively processes all HTML files from a mirror root
- Removes page chrome (navigation, footers, sidebars, cookie banners, etc.)
- Strips WordPress framework directories (wp-content, wp-includes, wp-json, etc.)
- Skips archive, pagination, and listing pages (preserves primary content only)
- Deduplicates by first 300 characters of normalized Markdown
- Outputs to a single concatenated Markdown file with page separators and metadata
- Comprehensive logging and error recovery (continues on failure)
- Configurable via module-level constants (reusable for any website mirror)

**Usage:**

```bash
uv run convert_mirror.py
```

Configuration (edit in script):
- `MIRROR_ROOT` — Path to wget-mirrored site
- `OUTPUT_DIR` — Directory for output files
- `OUTPUT_FILE` — Name of output Markdown file
- `SKIP_DIRS` — Directories to skip entirely

**Output:**

Single file with entries like:

```
--------------------------------------------------------------------------------
# Source

Path:
/products/cloud/index.html

Title:
Cloud Platform

--------------------------------------------------------------------------------

# Heading

Content here...
```

**Stats logged:**
- Total HTML files discovered
- Pages converted to Markdown
- Archive/pagination/listing pages skipped
- Duplicate pages skipped
- Files that failed to process
- Execution time
- Output file size
