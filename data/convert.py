# /// script
# requires-python = ">=3.12"
# ///
from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from docling.document_converter import DocumentConverter


DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"
MARKDOWN_DIR = Path(__file__).resolve().parent / "markdown"


def convert_downloads_to_markdown() -> dict:
    """Convert all HTML files in downloads to markdown, preserving year structure."""
    if MARKDOWN_DIR.exists():
        shutil.rmtree(MARKDOWN_DIR)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

    converter = DocumentConverter()
    manifest = load_manifest()
    converted_count = 0
    conversion_log = []

    for html_file in sorted(DOWNLOADS_DIR.rglob("*.htm*")):
        if html_file.name == "manifest.json":
            continue

        relative_path = html_file.relative_to(DOWNLOADS_DIR)
        year_dir = relative_path.parent
        md_dir = MARKDOWN_DIR / year_dir
        md_dir.mkdir(parents=True, exist_ok=True)

        md_path = md_dir / (html_file.stem + ".md")

        print(f"Converting {relative_path} → {md_path.relative_to(MARKDOWN_DIR)}")

        try:
            result = converter.convert(str(html_file))
            md_path.write_text(result.document.export_to_markdown(), encoding="utf-8")
            converted_count += 1
            conversion_log.append(
                {
                    "original": str(relative_path),
                    "converted": str(md_path.relative_to(MARKDOWN_DIR)),
                    "status": "success",
                }
            )
        except Exception as e:
            conversion_log.append(
                {
                    "original": str(relative_path),
                    "status": "failed",
                    "error": str(e),
                }
            )
            print(f"  ERROR: {e}")

    save_conversion_manifest(manifest, conversion_log, converted_count)
    return {
        "converted_count": converted_count,
        "output_dir": str(MARKDOWN_DIR),
        "conversion_log": conversion_log,
    }


def load_manifest() -> dict:
    """Load the downloads manifest if it exists."""
    manifest_path = DOWNLOADS_DIR / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {}


def save_conversion_manifest(
    original_manifest: dict, conversion_log: list, converted_count: int
) -> None:
    """Save conversion metadata to markdown folder."""
    conversion_manifest = {
        "source": "docling HTML-to-Markdown conversion",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "original_manifest": original_manifest,
        "converted_count": converted_count,
        "conversion_log": conversion_log,
    }
    manifest_path = MARKDOWN_DIR / "conversion_manifest.json"
    manifest_path.write_text(
        json.dumps(conversion_manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    result = convert_downloads_to_markdown()
    print(f"\nConverted {result['converted_count']} file(s) to {result['output_dir']}")
    print(f"Conversion manifest: {MARKDOWN_DIR / 'conversion_manifest.json'}")
