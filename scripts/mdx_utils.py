"""
mdx_utils.py   Shared helpers for MDX generation.
"""

import re


def first_sentence(text: str) -> str:
    """First sentence of a description, whitespace-collapsed (for frontmatter descriptions)."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return ""
    return re.split(r"(?<=[.!?])\s", text)[0].strip()


def mintlify_frontmatter(title: str, sidebar_title: str = "", description: str = "") -> list[str]:
    """
    YAML frontmatter lines for a Mintlify page. These MUST be the first lines of the file.

    Values are emitted as double-quoted scalars (whitespace-collapsed, inner double quotes
    downgraded to single) so colons/brackets in titles or descriptions can't break the YAML.
    Pass raw text   do NOT pre-escape with escape_mdx (frontmatter is YAML, not MDX body).
    """
    def q(s: str) -> str:
        s = re.sub(r"\s+", " ", (s or "").replace('"', "'")).strip()
        return f'"{s}"'

    out = ["---", f"title: {q(title)}"]
    if sidebar_title:
        out.append(f"sidebarTitle: {q(sidebar_title)}")
    if description:
        out.append(f"description: {q(description)}")
    out += ["---", ""]
    return out

# Matches backtick code spans to protect them from escaping
_CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1")
# Matches Markdown links [text](url) to protect link text from escaping
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def escape_mdx(text: str) -> str:
    """
    Escape characters that JSX/MDX would otherwise interpret in prose and table cells.

    Escapes < > { } while leaving backtick code spans and Markdown link syntax intact.
    """
    if not text:
        return text

    # Build a list of protected ranges (code spans and link hrefs that shouldn't be escaped)
    protected: list[tuple[int, int]] = []
    for m in _CODE_SPAN_RE.finditer(text):
        protected.append((m.start(), m.end()))
    for m in _LINK_RE.finditer(text):
        # Protect the URL portion only; link text still gets escaped
        protected.append((m.start(2), m.end(2)))

    def is_protected(pos: int) -> bool:
        return any(start <= pos < end for start, end in protected)

    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if is_protected(i):
            result.append(ch)
        elif ch == "<":
            result.append("&lt;")
        elif ch == ">":
            result.append("&gt;")
        elif ch == "{":
            result.append("&#123;")
        elif ch == "}":
            result.append("&#125;")
        else:
            result.append(ch)
        i += 1

    return "".join(result)
