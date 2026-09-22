#!/usr/bin/env python3

"""
Kindle My Clippings.txt -> Obsidian Markdown importer

Usage:
    python kindle_import.py "/path/to/My Clippings.txt"

The script:
- Reads the entire Kindle My Clippings.txt file.
- Groups highlights/notes by book.
- Ignores bookmarks.
- Creates one Markdown file per book.
- If a book already exists, adds only new highlights.
- Never duplicates existing highlights.
- Recalculates tags and keywords for affected books.
- Rebuilds Index.md from the actual Books/ directory.
- Uses ordinary Markdown links, compatible with Obsidian and GitHub.
- Runs completely offline.

Expected vault structure:

    YourVault/
    ├── Books/
    ├── Templates/
    ├── Index.md
    ├── Search Guide.md
    └── kindle_import.py
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOOKS_DIR_NAME = "Books"
INDEX_FILE_NAME = "Index.md"

# Number of keywords to keep per book.
MIN_KEYWORDS = 5
MAX_KEYWORDS = 15

# Number of thematic tags, excluding the mandatory books/highlights tags.
MAX_THEMATIC_TAGS = 8


# ---------------------------------------------------------------------------
# Tagging rules
#
# These are deliberately broad and stable. Keywords are extracted separately
# from the actual highlight text.
# ---------------------------------------------------------------------------

TAG_RULES = {
    "psychology": [
        r"\bpsycholog\w*",
        r"\bemotion\w*",
        r"\bbehavior\w*",
        r"\bbehaviour\w*",
        r"\bcognitive\b",
        r"\bthoughts?\b",
        r"\bfeelings?\b",
        r"\bmindset\b",
    ],

    "mental-health": [
        r"\bdepress\w*",
        r"\banxiet\w*",
        r"\bpanic\b",
        r"\btherapy\b",
        r"\btherap\w*",
        r"\btrauma\b",
        r"\bstress\b",
        r"\bmental health\b",
    ],

    "self-development": [
        r"\bself[- ]improv\w*",
        r"\bself[- ]develop\w*",
        r"\bpersonal growth\b",
        r"\bhabits?\b",
        r"\bdiscipline\b",
        r"\bmotivation\b",
        r"\bconfidence\b",
        r"\bself[- ]esteem\b",
    ],

    "work": [
        r"\bwork\b",
        r"\bworking\b",
        r"\bworkplace\b",
        r"\bemployee\w*",
        r"\bmanager\w*",
        r"\bteam\w*",
        r"\borganization\w*",
        r"\borganisation\w*",
    ],

    "career": [
        r"\bcareer\w*",
        r"\bprofession\w*",
        r"\bjob\b",
        r"\bemploy\w*",
        r"\boccupation\w*",
        r"\bexpertise\b",
        r"\bskills?\b",
    ],

    "creativity": [
        r"\bcreativ\w*",
        r"\bimagin\w*",
        r"\bartist\w*",
        r"\bart\b",
        r"\bdesign\w*",
        r"\bwriting\b",
        r"\bwriter\w*",
        r"\bcraft\w*",
    ],

    "money": [
        r"\bmoney\b",
        r"\bwealth\b",
        r"\bincome\b",
        r"\bsaving\w*",
        r"\bspend\w*",
        r"\bfinancial\w*",
        r"\bfinance\w*",
        r"\bbudget\w*",
    ],

    "investing": [
        r"\binvest\w*",
        r"\bstock\w*",
        r"\bbond\w*",
        r"\bportfolio\w*",
        r"\basset\w*",
        r"\bmarket\w*",
        r"\bdividend\w*",
        r"\bindex fund\w*",
    ],

    "relationships": [
        r"\brelationship\w*",
        r"\bmarriage\b",
        r"\bpartner\w*",
        r"\bfamily\b",
        r"\bfriend\w*",
        r"\blove\b",
        r"\battachment\b",
        r"\bintimacy\b",
    ],

    "philosophy": [
        r"\bphilosoph\w*",
        r"\bmeaning of life\b",
        r"\bexistential\w*",
        r"\bvirtue\b",
        r"\bethic\w*",
        r"\bmoral\w*",
        r"\bwisdom\b",
    ],

    "life-design": [
        r"\blife design\b",
        r"\blifestyle\b",
        r"\blife choices?\b",
        r"\bpurpose\b",
        r"\bmeaning\b",
        r"\bpriorit\w*",
        r"\bvalues?\b",
    ],

    "fear-and-anxiety": [
        r"\bfear\b",
        r"\bfears\b",
        r"\banxiet\w*",
        r"\bworry\b",
        r"\bworries\b",
        r"\buncertain\w*",
        r"\brisk\b",
    ],

    "craftsmanship": [
        r"\bcraftsmanship\b",
        r"\bcraft\b",
        r"\bmastery\b",
        r"\bpractice\b",
        r"\bdeliberate practice\b",
        r"\bexpertise\b",
        r"\bskill acquisition\b",
    ],

    "financial-advice": [
        r"\bfinancial advice\b",
        r"\bfinancial advisor\b",
        r"\bpersonal finance\b",
        r"\bretirement\b",
        r"\btaxes?\b",
        r"\bdebt\b",
        r"\bmortgage\b",
    ],

    "pop-culture": [
        r"\bfilm\b",
        r"\bmovie\b",
        r"\bmusic\b",
        r"\btelevision\b",
        r"\btv\b",
        r"\bcelebrity\b",
        r"\bpop culture\b",
    ],

    "wilderness": [
        r"\bwilderness\b",
        r"\bwild\b",
        r"\bnature\b",
        r"\bforest\b",
        r"\bmountain\w*",
        r"\bhiking\b",
        r"\bcamping\b",
    ],
}


# Common words that aren't useful as book-specific keywords.
STOPWORDS = {
    "about", "after", "again", "against", "almost", "also", "always",
    "because", "before", "being", "between", "could", "every", "first",
    "from", "have", "having", "into", "itself", "more", "most", "other",
    "over", "same", "should", "since", "some", "such", "than", "that",
    "their", "there", "these", "they", "this", "those", "through", "under",
    "very", "what", "when", "where", "which", "while", "with", "would",
    "your", "ours", "ourselves", "the", "and", "for", "you", "are", "was",
    "were", "has", "had", "not", "but", "can", "will", "one", "two",
    "three", "then", "them", "our", "out", "all", "any", "how", "why",
    "who", "whose", "its", "it's", "his", "her", "she", "him", "he",
    "we", "us", "do", "does", "did", "done", "too", "much", "many",
    "just", "like", "even", "only", "own", "get", "got", "getting",
    "make", "made", "makes", "making", "know", "think", "thought",
    "people", "person", "things", "thing", "way", "ways", "use", "used",
    "using", "new", "well", "may", "might", "must", "often", "really",
    "still", "rather", "here", "there", "back", "down", "up", "off",
}


# ---------------------------------------------------------------------------
# Kindle parsing
# ---------------------------------------------------------------------------

def parse_clippings(path: Path) -> dict[str, dict]:
    """
    Parse My Clippings.txt.

    Returns:

        {
            "Book Title": {
                "author": "Author Name",
                "clippings": [
                    "highlight text",
                    ...
                ]
            }
        }
    """

    raw = path.read_text(encoding="utf-8-sig", errors="replace")

    # Kindle separates clipping records with lines of equal signs.
    blocks = re.split(r"\n={10,}\s*\n", raw)

    books: dict[str, dict] = {}

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        lines = [line.strip() for line in block.splitlines()]

        if len(lines) < 3:
            continue

        title_author = lines[0]

        # Metadata line normally contains:
        # - Highlight
        # - Note
        # - Bookmark
        #
        # We deliberately ignore bookmarks.
        metadata_index = None

        for i, line in enumerate(lines[1:], start=1):
            if "Added on" in line:
                metadata_index = i
                break

        if metadata_index is None:
            continue

        metadata = lines[metadata_index]

        if "Bookmark" in metadata:
            continue

        # Everything after the metadata line is the actual clipping text.
        clipping_lines = lines[metadata_index + 1:]

        if not clipping_lines:
            continue

        clipping = " ".join(
            line.strip() for line in clipping_lines if line.strip()
        ).strip()

        if not clipping:
            continue

        title, author = split_title_author(title_author)

        if not title:
            continue

        if title not in books:
            books[title] = {
                "author": author,
                "clippings": [],
            }

        # Avoid duplicates already present in the Kindle export itself.
        if clipping not in books[title]["clippings"]:
            books[title]["clippings"].append(clipping)

    return books


def split_title_author(value: str) -> tuple[str, str]:
    """
    Kindle usually formats this as:

        Book Title (Author Name)

    Use the final ' (' so parentheses inside the title don't break parsing.
    """

    match = re.match(r"^(.*?)\s+\(([^()]*)\)\s*$", value)

    if match:
        title = match.group(1).strip()
        author = match.group(2).strip()
        return title, author

    return value.strip(), ""


# ---------------------------------------------------------------------------
# Filename handling
# ---------------------------------------------------------------------------

def safe_filename(title: str) -> str:
    """
    Produce a filesystem-safe Markdown filename.

    We preserve normal punctuation such as '-' and ':' where possible.
    """

    filename = title.strip()

    # Characters that are problematic on common operating systems.
    filename = re.sub(r'[\\/:*?"<>|#^]', "-", filename)

    # Collapse whitespace.
    filename = re.sub(r"\s+", " ", filename).strip()

    # Avoid trailing dots/spaces.
    filename = filename.rstrip(". ")

    # Keep filenames manageable.
    if len(filename) > 180:
        filename = filename[:180].rstrip()

    return filename


# ---------------------------------------------------------------------------
# Existing Markdown parsing
# ---------------------------------------------------------------------------

def extract_existing_highlights(path: Path) -> list[str]:
    """
    Extract highlight text from an existing book Markdown file.

    Highlights generated by this script are blockquotes:

        > Highlight text
    """

    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")

    highlights = []

    for line in text.splitlines():
        if line.startswith("> "):
            highlights.append(line[2:].strip())

    return highlights


def find_existing_book_file(
    books_dir: Path,
    title: str,
) -> Path | None:
    """
    Find the Markdown file corresponding to a title.

    First tries the deterministic filename generated by this script.
    Then falls back to frontmatter title matching, which makes the importer
    more tolerant of older vault files.
    """

    expected = books_dir / f"{safe_filename(title)}.md"

    if expected.exists():
        return expected

    # Fallback: inspect frontmatter titles.
    for path in books_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        match = re.search(
            r"^title:\s*[\"']?(.*?)[\"']?\s*$",
            text,
            flags=re.MULTILINE,
        )

        if match and match.group(1).strip() == title:
            return path

    return None


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def infer_tags(title: str, author: str, highlights: list[str]) -> list[str]:
    """
    Infer broad thematic tags from the whole book.
    """

    text = f"{title} {author} {' '.join(highlights)}".lower()

    scores = []

    for tag, patterns in TAG_RULES.items():
        score = 0

        for pattern in patterns:
            score += len(re.findall(pattern, text, flags=re.IGNORECASE))

        if score:
            scores.append((score, tag))

    # Strongest themes first.
    scores.sort(key=lambda item: (-item[0], item[1]))

    tags = ["books", "highlights"]

    for _, tag in scores[:MAX_THEMATIC_TAGS]:
        tags.append(tag)

    return tags


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def normalize_word(word: str) -> str:
    """
    Normalize simple keyword candidates.
    """

    word = word.lower().strip()

    # A modest amount of stemming to combine common variants.
    replacements = {
        "psychological": "psychology",
        "psychologically": "psychology",
        "relationships": "relationship",
        "emotions": "emotion",
        "emotional": "emotion",
        "behaviors": "behavior",
        "behaviours": "behavior",
        "decisions": "decision",
        "decision-making": "decision making",
        "investments": "investment",
        "investing": "investment",
        "creativities": "creativity",
        "habits": "habit",
        "skills": "skill",
        "careers": "career",
        "experiences": "experience",
    }

    return replacements.get(word, word)


def extract_keywords(
    title: str,
    author: str,
    highlights: list[str],
) -> list[str]:
    """
    Extract useful book-specific keywords from the highlight corpus.

    This intentionally uses lightweight offline text analysis rather than
    an external AI/API service.
    """

    text = " ".join(highlights).lower()

    # First collect useful multi-word phrases that are especially valuable
    # for knowledge retrieval.
    phrase_candidates = [
        "cognitive behavioral therapy",
        "cognitive behavioural therapy",
        "cognitive distortions",
        "deliberate practice",
        "personal development",
        "self development",
        "self improvement",
        "mental health",
        "personal finance",
        "financial independence",
        "decision making",
        "emotional intelligence",
        "negative thinking",
        "positive thinking",
        "critical thinking",
        "creative process",
        "creative work",
        "professional development",
        "work life balance",
        "life design",
        "long term",
        "short term",
        "compound interest",
        "risk management",
        "behavioral economics",
        "behavioural economics",
        "social psychology",
        "human behavior",
        "human behaviour",
        "self esteem",
        "self-worth",
        "meaning of life",
    ]

    phrase_counts = Counter()

    for phrase in phrase_candidates:
        count = text.count(phrase)
        if count:
            phrase_counts[phrase] = count

    # Individual word frequencies.
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{3,}", text)

    word_counts = Counter()

    for word in words:
        word = normalize_word(word)

        if word in STOPWORDS:
            continue

        # Ignore very generic words.
        if len(word) < 4:
            continue

        word_counts[word] += 1

    # Remove words that are overwhelmingly common in ordinary prose.
    generic = {
        "something", "someone", "anything", "everything", "nothing",
        "another", "however", "important", "different", "actually",
        "example", "perhaps", "possible", "probably", "already",
        "around", "without", "within", "throughout", "between",
    }

    for word in generic:
        word_counts.pop(word, None)

    # Combine phrases and words. Phrase matches receive extra weight.
    candidates = []

    for phrase, count in phrase_counts.items():
        candidates.append((count * 4, phrase))

    for word, count in word_counts.items():
        candidates.append((count, word))

    candidates.sort(key=lambda item: (-item[0], item[1]))

    keywords = []

    for _, candidate in candidates:
        if candidate not in keywords:
            keywords.append(candidate)

        if len(keywords) >= MAX_KEYWORDS:
            break

    # If a very short book doesn't produce enough keywords, that's okay.
    # Don't manufacture keywords.
    return keywords


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def yaml_quote(value: str) -> str:
    """
    Quote a YAML string safely.
    """

    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def build_frontmatter(
    title: str,
    author: str,
    tags: list[str],
    keywords: list[str],
) -> str:

    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"author: {yaml_quote(author)}",
        "type: book",
        "tags:",
    ]

    for tag in tags:
        lines.append(f"  - {tag}")

    lines.append("keywords:")

    for keyword in keywords:
        lines.append(f"  - {yaml_quote(keyword)}")

    lines.append("---")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Book Markdown generation
# ---------------------------------------------------------------------------

def build_book_markdown(
    title: str,
    author: str,
    highlights: list[str],
) -> str:

    tags = infer_tags(title, author, highlights)
    keywords = extract_keywords(title, author, highlights)

    frontmatter = build_frontmatter(
        title,
        author,
        tags,
        keywords,
    )

    lines = [
        frontmatter,
        "",
        f"# {title}",
        "",
    ]

    if author:
        lines.extend([
            f"**Author:** {author}",
            "",
        ])

    lines.extend([
        "## Highlights",
        "",
    ])

    for highlight in highlights:
        lines.append(f"> {highlight}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Updating existing books
# ---------------------------------------------------------------------------

def update_book_file(
    path: Path,
    title: str,
    author: str,
    kindle_highlights: list[str],
) -> tuple[bool, int]:

    existing_highlights = extract_existing_highlights(path)

    existing_set = set(existing_highlights)

    new_highlights = [
        h for h in kindle_highlights
        if h not in existing_set
    ]

    if not new_highlights:
        return False, 0

    all_highlights = existing_highlights + new_highlights

    content = build_book_markdown(
        title=title,
        author=author,
        highlights=all_highlights,
    )

    path.write_text(content, encoding="utf-8")

    return True, len(new_highlights)


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------

def count_highlights_in_book(path: Path) -> int:
    return len(extract_existing_highlights(path))


def markdown_link(text: str, relative_path: str) -> str:
    """
    Create a normal Markdown link.

    URL-encodes spaces and special characters in the target path while
    leaving ordinary filename characters readable.
    """

    encoded_path = quote(relative_path, safe="/-_.()")

    return f"[{text}]({encoded_path})"


def extract_title_from_book(path: Path) -> str:
    """
    Read title from YAML frontmatter, falling back to filename.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return path.stem

    match = re.search(
        r"^title:\s*[\"']?(.*?)[\"']?\s*$",
        text,
        flags=re.MULTILINE,
    )

    if match:
        return match.group(1).strip()

    return path.stem


def rebuild_index(vault_dir: Path) -> tuple[int, int]:

    books_dir = vault_dir / BOOKS_DIR_NAME
    index_path = vault_dir / INDEX_FILE_NAME

    book_files = sorted(
        books_dir.glob("*.md"),
        key=lambda p: extract_title_from_book(p).lower(),
    )

    total_books = len(book_files)

    total_highlights = sum(
        count_highlights_in_book(path)
        for path in book_files
    )

    lines = [
        "# Kindle Highlights",
        "",
        f"**Books:** {total_books}  ",
        f"**Highlights:** {total_highlights}",
        "",
        "## Books",
        "",
    ]

    for path in book_files:
        title = extract_title_from_book(path)

        # Index.md lives one level above Books/.
        relative_path = f"{BOOKS_DIR_NAME}/{path.name}"

        lines.append(
            markdown_link(title, relative_path)
        )

    lines.append("")

    index_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return total_books, total_highlights


# ---------------------------------------------------------------------------
# Main import operation
# ---------------------------------------------------------------------------

def import_clippings(
    clippings_path: Path,
    vault_dir: Path,
) -> int:

    if not clippings_path.exists():
        print(f"ERROR: Clippings file does not exist:")
        print(f"  {clippings_path}")
        return 1

    if not clippings_path.is_file():
        print(f"ERROR: Not a file:")
        print(f"  {clippings_path}")
        return 1

    books_dir = vault_dir / BOOKS_DIR_NAME
    books_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("Kindle → Obsidian importer")
    print("=" * 40)
    print(f"Source: {clippings_path}")
    print(f"Vault:  {vault_dir}")
    print()

    books = parse_clippings(clippings_path)

    if not books:
        print("No highlights or notes were found.")
        print()
        return 0

    source_highlights = sum(
        len(book["clippings"])
        for book in books.values()
    )

    print(
        f"Found {len(books)} books and "
        f"{source_highlights} highlights/notes in source."
    )
    print()

    created_books = 0
    updated_books = 0
    unchanged_books = 0
    new_highlights = 0

    for title in sorted(books.keys(), key=str.lower):

        data = books[title]

        author = data["author"]
        kindle_highlights = data["clippings"]

        existing_file = find_existing_book_file(
            books_dir,
            title,
        )

        if existing_file is None:

            filename = safe_filename(title) + ".md"
            book_path = books_dir / filename

            content = build_book_markdown(
                title=title,
                author=author,
                highlights=kindle_highlights,
            )

            book_path.write_text(
                content,
                encoding="utf-8",
            )

            created_books += 1
            new_highlights += len(kindle_highlights)

            print(
                f"CREATE  {title} "
                f"({len(kindle_highlights)} highlights)"
            )

        else:

            changed, added = update_book_file(
                path=existing_file,
                title=title,
                author=author,
                kindle_highlights=kindle_highlights,
            )

            if changed:
                updated_books += 1
                new_highlights += added

                print(
                    f"UPDATE  {title} "
                    f"(+{added} highlights)"
                )
            else:
                unchanged_books += 1

                print(
                    f"SKIP    {title} "
                    f"(no new highlights)"
                )

    # Always rebuild from the actual Markdown files.
    total_books, total_highlights = rebuild_index(
        vault_dir
    )

    print()
    print("=" * 40)
    print("Import complete")
    print("=" * 40)
    print(f"New books:          {created_books}")
    print(f"Updated books:      {updated_books}")
    print(f"Unchanged books:    {unchanged_books}")
    print(f"New highlights:     {new_highlights}")
    print()
    print(f"Total books:        {total_books}")
    print(f"Total highlights:   {total_highlights}")
    print()
    print("Index.md rebuilt.")
    print()

    return 0


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Import Kindle My Clippings.txt into an Obsidian vault."
        )
    )

    parser.add_argument(
        "clippings",
        type=Path,
        help="Path to Kindle My Clippings.txt",
    )

    parser.add_argument(
        "--vault",
        type=Path,
        default=Path.cwd(),
        help=(
            "Obsidian vault directory. "
            "Defaults to the current directory."
        ),
    )

    args = parser.parse_args()

    vault_dir = args.vault.resolve()
    clippings_path = args.clippings.expanduser().resolve()

    # Make sure this really looks like an Obsidian vault.
    if not vault_dir.exists():
        print(f"ERROR: Vault directory does not exist: {vault_dir}")
        return 1

    return import_clippings(
        clippings_path=clippings_path,
        vault_dir=vault_dir,
    )


if __name__ == "__main__":
    sys.exit(main())