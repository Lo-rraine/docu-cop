#!/usr/bin/env python3
"""
Clean 4s4_raw.md by removing obvious spam sections.
Spam includes: betting platforms, casinos, gambling content.
"""

import re
from pathlib import Path


def is_spam_section(section: dict) -> bool:
    """Return True if this section is obvious spam."""
    text = " ".join([
        section.get("title") or "",
        section.get("source") or "",
        (section.get("content") or "")[:1000],  # only inspect the start
    ]).lower()

    spam_patterns = [
        r"\b1xbet\b",
        r"\b1win\b",
        r"\bmelbet\b",
        r"\b22bet\b",
        r"\bbetano\b",
        r"\bbet365\b",
        r"\bparipesa\b",
        r"\bcasino\b",
        r"\bgambling\b",
        r"\bbookmaker\b",
        r"\bslot\b",
        r"\bpoker\b",
        r"\broulette\b",
        r"\bblackjack\b",
        r"\bjackpot\b",
    ]

    return any(re.search(pattern, text, re.IGNORECASE) for pattern in spam_patterns)


def extract_sections(content: str) -> list[dict]:
    """Extract sections from markdown separated by ---- delimiters."""
    sections = []
    parts = content.split("--------------------------------------------------------------------------------")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract metadata
        source_match = re.search(r"Path:\s*([^\n]+)", part)
        title_match = re.search(r"Title:\s*([^\n]+)", part)

        source_path = source_match.group(1).strip() if source_match else None
        title = title_match.group(1).strip() if title_match else None

        sections.append({
            "source": source_path,
            "title": title,
            "content": part,
        })

    return sections


def clean_4s4_raw():
    """Main cleaning function."""
    raw_file = Path("data/4s4_raw.md")

    if not raw_file.exists():
        print(f"File not found: {raw_file}")
        return

    content = raw_file.read_text(encoding="utf-8")
    sections = extract_sections(content)

    # Filter out spam
    clean_sections = [s for s in sections if not is_spam_section(s)]

    print(f"[INFO] Total sections: {len(sections)}")
    print(f"[INFO] Spam removed: {len(sections) - len(clean_sections)}")
    print(f"[INFO] Clean sections kept: {len(clean_sections)}")

    # Rebuild document
    cleaned_content = "\n\n".join([s["content"] for s in clean_sections])

    # Write output with specified filename
    output_file = Path("data/2026") / "4s4_10-k_2026-06-20_0001045980-000012.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(cleaned_content, encoding="utf-8")

    print(f"[INFO] Cleaned file created: {output_file}")


if __name__ == "__main__":
    clean_4s4_raw()
