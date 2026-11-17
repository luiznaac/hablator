"""The legacy adapter's HTML -> plain-text derivation (the new API path never derives one)."""

from __future__ import annotations

from hablator.httpapi.legacy_text import strip_html


def test_tags_are_stripped_and_inline_text_is_joined() -> None:
    assert strip_html("<p>Backup <b>done</b>.</p>") == "Backup done."


def test_block_boundaries_become_blank_line_separated_paragraphs() -> None:
    assert strip_html("<p>first</p><p>second</p>") == "first\n\nsecond"


def test_entities_are_unescaped() -> None:
    assert strip_html("<p>a &amp; b &lt;c&gt;</p>") == "a & b <c>"


def test_line_breaks_and_list_items_separate_lines() -> None:
    assert strip_html("<p>one<br>two</p><ul><li>three</li><li>four</li></ul>") == ("one\ntwo\n\nthree\nfour")


def test_plain_text_without_markup_is_returned_trimmed() -> None:
    assert strip_html("  just text  ") == "just text"
