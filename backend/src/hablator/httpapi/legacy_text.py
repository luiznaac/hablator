"""Plain-text derivation for the legacy `/send-email` adapter.

The legacy contract sends its `text` field as HTML. To give those mails a plain-text alternative
without changing how they render, the adapter keeps the HTML as `body_html` and derives a
`body_text` with the stdlib parser: tags stripped, entities unescaped, block boundaries turned
into newlines. The new API path never derives a plain part; only this legacy adapter does.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_PARAGRAPH_TAGS = frozenset(
    {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "pre",
        "ul",
        "ol",
        "table",
        "section",
        "article",
        "header",
        "footer",
        "hr",
    }
)
_BREAK_TAGS = frozenset({"br"})
_ROW_TAGS = frozenset({"li", "tr"})

_BLANK_LINE_RUN = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._emit(tag, line_tags=_BREAK_TAGS)

    def handle_endtag(self, tag: str) -> None:
        self._emit(tag, line_tags=_ROW_TAGS)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._emit(tag, line_tags=_BREAK_TAGS)

    def _emit(self, tag: str, *, line_tags: frozenset[str]) -> None:
        if tag in _PARAGRAPH_TAGS:
            self._parts.append("\n\n")
        elif tag in line_tags:
            self._parts.append("\n")

    def text(self) -> str:
        collapsed = _BLANK_LINE_RUN.sub("\n\n", "".join(self._parts))
        return collapsed.strip()


def strip_html(markup: str) -> str:
    """Return a readable plain-text rendering of an HTML fragment."""
    extractor = _TextExtractor()
    extractor.feed(markup)
    extractor.close()
    return extractor.text()
