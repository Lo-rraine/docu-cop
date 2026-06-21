#!/usr/bin/env python3
"""
Convert a wget-mirrored website into a deduplicated Markdown corpus.
Optimized for completeness, deterministic output, and low noise.

Usage:
    python convert_mirror.py [--mirror-root PATH] [--output-file PATH]

Configure via module-level constants or command-line arguments for reusability.
"""

import copy
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import html2text
from bs4 import BeautifulSoup, Tag

# ============================================================================
# Configuration (override via module constants or CLI args)
# ============================================================================

MIRROR_ROOT = Path(r"C:\Users\Lorraine\www.4s4.io")
OUTPUT_DIR = Path(r"C:\Users\Lorraine\Development\docu-co\data")
OUTPUT_FILE = OUTPUT_DIR / "4s4_raw.md"

SKIP_DIRS = {"wp-content", "wp-json", "wp-includes", "feed", "comments"}
CHROME_TAGS = {"nav", "header", "footer", "aside"}
CHROME_KEYWORDS = {
    "menu", "cookie", "sidebar", "widget", "newsletter", "social",
    "back-to-top", "breadcrumb", "pagination", "share",
    "related-posts", "site-footer", "site-header"
}

# ============================================================================
# Logging setup
# ============================================================================

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ============================================================================
# Discovery
# ============================================================================

def discover_html_files(root: Path, skip_dirs: set[str]) -> list[Path]:
    """Recursively discover all .html files, skipping framework dirs."""
    files = []
    for html_file in root.rglob("*.html"):
        # Skip files in excluded directories
        if any(part in skip_dirs for part in html_file.parts):
            continue
        # Skip wget query-string artifacts
        if "@" in html_file.name or "%" in html_file.name:
            continue
        files.append(html_file)
    return sorted(files)

# ============================================================================
# Page classification
# ============================================================================

def is_year_archive(path: Path) -> bool:
    """Check if path is a year directory (e.g., 2024)."""
    if not path.parts:
        return False
    first_part = path.parts[0]
    return first_part.isdigit() and 2000 <= int(first_part) < 2050

def is_date_archive(path: Path) -> bool:
    """Check if path contains date parts (YYYY/MM/DD pattern)."""
    parts = path.parts[:-1]  # Exclude filename
    # Look for two consecutive numeric parts (MM/DD)
    for i in range(len(parts) - 1):
        p1, p2 = parts[i], parts[i + 1]
        if (p1.isdigit() and len(p1) == 2 and
            p2.isdigit() and len(p2) == 2):
            return True
    return False

def is_pagination_page(path: Path) -> bool:
    """Check if path contains pagination (page/N)."""
    return any(part == "page" for part in path.parts)

def is_taxonomy_archive(path: Path) -> bool:
    """Check if path is a category or tag archive."""
    return any(part in {"category", "tag"} for part in path.parts)

def is_author_archive(path: Path) -> bool:
    """Check if path is an author archive."""
    return any(part == "author" for part in path.parts)

def has_listing_body_class(soup: BeautifulSoup) -> bool:
    """Check if body has archive/listing CSS classes."""
    try:
        body = soup.find("body")
        if not body:
            return False
        body_class = body.get("class", []) or []
        if isinstance(body_class, str):
            body_class = body_class.split()
        listing_keywords = {"archive", "search-results", "paged"}
        for kw in listing_keywords:
            if any(kw in cls for cls in body_class):
                return True
    except (AttributeError, TypeError):
        return False
    return False

def is_single_post_page(soup: BeautifulSoup) -> bool:
    """Check if this is a single post/page (not a listing)."""
    try:
        body = soup.find("body")
        if not body:
            return False
        body_class = body.get("class", []) or []
        if isinstance(body_class, str):
            body_class = body_class.split()
        # WordPress marks single posts/pages with 'single' or 'post' class
        single_keywords = {"single", "single-post", "single-page"}
        return any(kw in body_class for kw in single_keywords)
    except (AttributeError, TypeError):
        return False

def is_multi_article_listing(soup: BeautifulSoup) -> bool:
    """Check if page contains 3+ article elements and is NOT a single post."""
    # Single posts/pages can have multiple articles (main + related), so exclude them
    if is_single_post_page(soup):
        return False
    articles = soup.find_all("article")
    return len(articles) >= 3

def classify_page(path: Path, root: Path, soup: BeautifulSoup) -> tuple[bool, Optional[str]]:
    """
    Classify a page and determine if it should be skipped.
    Returns (should_skip, reason_tag).
    """
    if is_year_archive(path):
        return True, "archive"

    if is_date_archive(path):
        return True, "archive"

    if is_pagination_page(path):
        return True, "pagination"

    if is_taxonomy_archive(path):
        return True, "archive"

    if is_author_archive(path):
        return True, "archive"

    if has_listing_body_class(soup):
        return True, "archive"

    if is_multi_article_listing(soup):
        return True, "listing"

    return False, None

# ============================================================================
# DOM cleanup
# ============================================================================

def score_container(element: Tag) -> int:
    """
    Score a container based on content density.

    Scores based on:
    - Headings (h1-h6): +20 each
    - Paragraphs (p): +10 each
    - Text length: +1 per 100 chars
    - Lists (ul, ol): +30 each
    - Tables: +50 each

    Penalizes (big negative) if contains keywords like footer, nav, sidebar, menu, etc.
    """
    score = 0

    # Count content elements
    headings = len(element.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
    paragraphs = len(element.find_all("p", recursive=True))
    lists = len(element.find_all(["ul", "ol"]))
    tables = len(element.find_all("table"))
    text_length = len(element.get_text(strip=True))

    score += headings * 20
    score += paragraphs * 10
    score += lists * 30
    score += tables * 50
    score += max(0, text_length // 100)

    # Penalize containers with chrome keywords
    element_html = str(element).lower()
    penalize_keywords = {
        "footer", "nav", "sidebar", "menu", "breadcrumb", "social",
        "widget", "cookie", "newsletter", "pagination", "related", "comment"
    }
    for keyword in penalize_keywords:
        if keyword in element_html:
            score -= 100

    return score


def find_content_root(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Identify the primary content container using content-density scoring.

    Handles both traditional WordPress and Elementor page builders by:
    1. Detecting Elementor pages (looking for .elementor class)
    2. Scoring all substantial containers based on content density
    3. Returning the highest-scoring container
    4. Falling back to body if no good candidate found
    """
    # Detect Elementor pages
    elementor = soup.find(class_="elementor")
    is_elementor_page = elementor is not None
    logger.debug(f"Elementor page detected: {is_elementor_page}")

    # Collect candidate containers
    candidates = []

    # Primary candidates: semantic containers
    for selector_name, element in [
        ("main", soup.find("main")),
        ("article", soup.find("article")),
        ("div.entry-content", soup.find("div", class_="entry-content")),
        ("div.post-content", soup.find("div", class_="post-content")),
        ("div.page-content", soup.find("div", class_="page-content")),
        ("div.content", soup.find("div", class_="content")),
        ("div#content", soup.find("div", id="content")),
    ]:
        if element and len(element.get_text(strip=True)) > 100:
            candidates.append((selector_name, element))

    # For Elementor pages, also consider Elementor containers
    if is_elementor_page:
        # Look for the main Elementor container
        elementor_main = soup.find("div", class_="elementor")
        if elementor_main:
            candidates.append(("div.elementor", elementor_main))

        # Also consider individual Elementor sections
        elementor_sections = soup.find_all("div", class_="elementor-section")
        for i, section in enumerate(elementor_sections):
            if len(section.get_text(strip=True)) > 100:
                candidates.append((f"elementor-section-{i}", section))

        # And Elementor containers
        elementor_containers = soup.find_all("div", class_="elementor-container")
        for i, container in enumerate(elementor_containers):
            if len(container.get_text(strip=True)) > 100:
                candidates.append((f"elementor-container-{i}", container))

    # Add large sections and divs as secondary candidates
    for section in soup.find_all("section"):
        if len(section.get_text(strip=True)) > 200:
            candidates.append(("section", section))

    # Score all candidates and pick the best
    if candidates:
        best_name, best_element = max(
            candidates,
            key=lambda x: score_container(x[1]),
            default=(None, None)
        )

        if best_element:
            best_score = score_container(best_element)
            if best_score > 50:  # Arbitrary minimum score threshold
                logger.debug(f"Found content root: {best_name} (score: {best_score})")
                return best_element

    # Last resort: use body
    body = soup.find("body")
    if body:
        body_score = score_container(body)
        logger.debug(f"Falling back to <body> (score: {body_score})")
        return body

    logger.warning("Could not identify content root")
    return soup


def extract_content(html: str) -> tuple[str, str]:
    """
    Extract title and primary content with content-density-based selection.

    Strategy:
    1. Find the highest-scoring content container (by semantic density)
    2. Deep-copy the selected container (avoids reparsing issues)
    3. Remove chrome elements (nav, footer, aside tags) from the copy
    4. Return the cleaned HTML fragment for markdown conversion
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "(Untitled)"

    # Find the best content container using semantic density scoring
    content_root = find_content_root(soup)

    if not content_root:
        return title, ""

    # Verify we have substantial content
    text_content = content_root.get_text(strip=True)
    if len(text_content) < 50:
        logger.debug("Content root has insufficient text, falling back to body")
        content_root = soup.find("body") or soup

    # Deep-copy the content root to avoid modifying the original
    try:
        content_clone = copy.deepcopy(content_root)
    except Exception as e:
        logger.warning(f"Failed to deepcopy content root: {e}")
        return title, ""

    # Remove chrome tags from the cloned subtree
    for tag_name in CHROME_TAGS:
        for tag in content_clone.find_all(tag_name):
            try:
                tag.decompose()
            except:
                pass

    return title, str(content_clone)

# ============================================================================
# Markdown conversion
# ============================================================================

def to_markdown(html_fragment: str) -> str:
    """Convert HTML fragment to Markdown using html2text."""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    h.ignore_links = False
    h.unicode_snob = True
    h.mark_code = True
    h.ignore_emphasis = False
    h.protect_links = True
    h.wrap_links = False
    return h.handle(html_fragment)

# ============================================================================
# Normalization and deduplication
# ============================================================================

def normalize(md: str) -> str:
    """Normalize Markdown: collapse whitespace, strip trailing spaces."""
    lines = md.split("\n")
    normalized = [line.rstrip() for line in lines]

    # Collapse 3+ consecutive blank lines to 2
    result = []
    blank_count = 0
    for line in normalized:
        if line.strip():
            result.append(line)
            blank_count = 0
        else:
            blank_count += 1
            if blank_count <= 2:
                result.append(line)

    return "\n".join(result).strip()

def dedup_key(md: str) -> str:
    """Generate a deduplication key from the first 300 characters."""
    return md[:300].strip()

# ============================================================================
# Page header formatting
# ============================================================================

def page_header(rel_path: str, title: str) -> str:
    """Format a page header with separator."""
    # Convert backslashes to forward slashes for consistency
    rel_path = rel_path.replace("\\", "/")
    return (
        "--------------------------------------------------------------------------------\n"
        "# Source\n"
        "\n"
        f"Path:\n"
        f"/{rel_path}\n"
        "\n"
        f"Title:\n"
        f"{title}\n"
        "\n"
        "--------------------------------------------------------------------------------\n"
    )

# ============================================================================
# Main processing
# ============================================================================

def process_file(
    path: Path,
    root: Path,
) -> Optional[tuple[str, str]]:
    """
    Process a single HTML file.
    Returns (title, markdown) or None if skipped/classified as listing.
    Raises exception on hard failure (caller catches and records).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {path}: {e}")
        raise

    # Parse and classify
    soup = BeautifulSoup(html_content, "html.parser")
    should_skip, reason = classify_page(path, root, soup)

    if should_skip:
        rel_path = path.relative_to(root)
        logger.debug(f"Skipped (reason={reason}): {rel_path}")
        return None

    # Extract and convert
    title, html_fragment = extract_content(html_content)
    markdown = to_markdown(html_fragment)
    markdown = normalize(markdown)

    return title, markdown

# ============================================================================
# Main execution
# ============================================================================

def main():
    """Main entry point."""
    start_time = time.time()

    logger.info("Starting conversion...")
    logger.info(f"Mirror root: {MIRROR_ROOT}")
    logger.info(f"Output file: {OUTPUT_FILE}")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Discover files
    files = discover_html_files(MIRROR_ROOT, SKIP_DIRS)
    logger.info(f"Discovered {len(files)} HTML files")

    # Initialize deduplication and counters
    seen_keys: set[str] = set()
    stats = {
        "discovered": len(files),
        "converted": 0,
        "duplicates": 0,
        "skipped_purpose": 0,  # Archives, pagination, listings
        "skipped_dir_rule": 0,  # Directory skip rules
        "skipped_error": 0,
    }
    skip_reasons: dict[str, int] = {}
    failed_files: list[tuple[str, str]] = []

    # Create h2t converter once
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    h.ignore_links = False
    h.unicode_snob = True
    h.mark_code = True
    h.ignore_emphasis = False
    h.protect_links = True
    h.wrap_links = False

    # Process files
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for i, path in enumerate(files, 1):
            rel_path = path.relative_to(MIRROR_ROOT)
            logger.debug(f"[{i}/{len(files)}] Processing {rel_path}")

            try:
                result = process_file(path, MIRROR_ROOT)

                if result is None:
                    stats["skipped_purpose"] += 1
                    # Count by reason
                    try:
                        soup = BeautifulSoup(
                            open(path, "r", encoding="utf-8", errors="replace").read(),
                            "html.parser"
                        )
                        _, reason = classify_page(path, MIRROR_ROOT, soup)
                        if reason:
                            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                    except:
                        pass
                    continue

                title, markdown = result

                # Check for duplicate
                key = dedup_key(markdown)
                if key in seen_keys:
                    stats["duplicates"] += 1
                    logger.debug(f"Skipped duplicate: {rel_path}")
                    continue

                seen_keys.add(key)
                stats["converted"] += 1

                # Write to output
                header = page_header(str(rel_path), title)
                out.write(header)
                out.write(markdown)
                out.write("\n\n")

                if i % 20 == 0:
                    logger.info(f"Converted {stats['converted']} pages so far...")

            except Exception as e:
                stats["skipped_error"] += 1
                failed_files.append((str(rel_path), str(e)))
                logger.error(f"Failed to process {rel_path}: {e}")
                continue

    # Calculate final stats
    elapsed = time.time() - start_time
    output_size = OUTPUT_FILE.stat().st_size / (1024 * 1024)  # MB

    # Print summary
    print("\n" + "=" * 80)
    print("Conversion complete")
    print("=" * 80)
    print(f"HTML files discovered    : {stats['discovered']}")
    print(f"Pages converted          : {stats['converted']}")
    if skip_reasons:
        reason_str = ", ".join(f"{k}:{v}" for k, v in sorted(skip_reasons.items()))
        print(f"Listing/archive skipped  : {stats['skipped_purpose']}  ({reason_str})")
    else:
        print(f"Listing/archive skipped  : {stats['skipped_purpose']}")
    print(f"Duplicates skipped       : {stats['duplicates']}")
    print(f"Files skipped (dir rule) : {stats['skipped_dir_rule']}")
    print(f"Files skipped (error)    : {stats['skipped_error']}")
    print(f"Execution time           : {elapsed:.1f}s")
    print(f"Output file size         : {output_size:.2f} MB")
    print(f"Output file              : {OUTPUT_FILE}")

    if failed_files:
        print("\nFailed files:")
        for path, error in failed_files:
            print(f"  {path}: {error}")

    print("=" * 80 + "\n")

    logger.info("Conversion complete")

if __name__ == "__main__":
    main()
