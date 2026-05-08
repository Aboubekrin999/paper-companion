"""
arXiv reference parser.

Accepts URLs, raw IDs, or `arxiv:` prefixed strings; returns the canonical
ID, version (if specified), and stable abs/pdf URLs. No network calls — the
fetcher lives in a sibling module so this stays trivially testable.

Supports both ID schemes:
- New (post-2007.04): `YYMM.NNNNN[vN]`, e.g. `2401.12345`, `2401.12345v2`.
- Old (pre-2007.04): `archive[.SC]/NNNNNNN[vN]`, e.g. `cs/0301001`,
  `math.GT/0309136v1`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# New-style IDs use 4 or 5 digits after the dot. Versions are optional.
_NEW_ID = re.compile(r"\b(\d{4}\.\d{4,5})(?:v(\d+))?\b")

# Old-style IDs: archive name (letters, may include dash and a 2-letter
# subcategory after a dot) / 7 digits, optional version.
_OLD_ID = re.compile(
    r"\b([a-z][a-z\-]*(?:\.[A-Z]{2})?/\d{7})(?:v(\d+))?\b"
)


@dataclass(frozen=True)
class ArxivPaper:
    """Canonical reference to an arXiv paper."""

    id: str
    """Canonical ID without version, e.g. ``2401.12345`` or ``cs/0301001``."""

    version: int | None
    """Explicit version if the input specified one, else None."""

    abs_url: str
    """Canonical abstract page URL (``https://arxiv.org/abs/<id>``)."""

    pdf_url: str
    """Canonical PDF URL (``https://arxiv.org/pdf/<id>.pdf``)."""


def parse_arxiv(reference: str) -> ArxivPaper | None:
    """
    Extract an arXiv paper from a URL, raw ID, or ``arxiv:`` prefixed string.

    Returns ``None`` if no recognizable arXiv ID is present. The check is
    deliberately permissive — anything that contains a valid ID is accepted,
    so dropping a copy-pasted citation works as expected.
    """
    if not reference:
        return None

    # Try the new format first; it's the common case.
    match = _NEW_ID.search(reference)
    if match is None:
        match = _OLD_ID.search(reference)
    if match is None:
        return None

    canonical = match.group(1)
    version_str = match.group(2)
    version = int(version_str) if version_str else None

    return ArxivPaper(
        id=canonical,
        version=version,
        abs_url=f"https://arxiv.org/abs/{canonical}",
        pdf_url=f"https://arxiv.org/pdf/{canonical}.pdf",
    )
