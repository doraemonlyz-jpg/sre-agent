"""Unit tests for the markdown runbook chunker."""

from __future__ import annotations

from sre_agent.runbooks.chunker import chunk_text


def test_basic_chunk_split() -> None:
    md = """# Top title

intro prose should be dropped

## First section

> service: checkout-api
> tags: redis, latency

body of first section

## Second section

body of second section
"""
    chunks = chunk_text(md, path="x.md")
    assert len(chunks) == 2
    first, second = chunks
    assert first.title == "First section"
    assert first.service == "checkout-api"
    assert first.tags == ["redis", "latency"]
    assert "body of first section" in first.body
    assert second.title == "Second section"
    assert second.service is None
    assert second.tags == []


def test_chunks_with_no_metadata_still_parse() -> None:
    md = """# Title
intro

## Just a section
plain body, no metadata at all.

more body.
"""
    [chunk] = chunk_text(md, path="y.md")
    assert chunk.title == "Just a section"
    assert chunk.service is None
    assert chunk.tags == []
    assert "plain body" in chunk.body


def test_file_with_no_sections_returns_empty() -> None:
    """A file with only a `# Title` and no `## ` sections should yield zero chunks."""
    md = "# Only a top-level title\n\nNo sections here."
    assert chunk_text(md) == []


def test_long_body_is_trimmed() -> None:
    long_body = "lorem " * 1000  # ~6000 chars
    md = f"# T\n\n## Section\n\n{long_body}"
    [chunk] = chunk_text(md)
    assert chunk.body.endswith("…")
    assert len(chunk.body) <= 2300


def test_metadata_parsing_is_case_insensitive_on_keys() -> None:
    md = """# T
## Section
> Service: foo
> Tags: a, b

body
"""
    [chunk] = chunk_text(md)
    assert chunk.service == "foo"
    assert chunk.tags == ["a", "b"]


def test_blank_lines_between_metadata_are_tolerated() -> None:
    md = """# T

## Section

> service: foo

> tags: a, b

real body line.
"""
    [chunk] = chunk_text(md)
    assert chunk.service == "foo"
    assert chunk.tags == ["a", "b"]
    assert "real body line." in chunk.body


def test_search_text_concatenates_title_and_body() -> None:
    md = "# T\n## Hello World\n\nbody content here"
    [chunk] = chunk_text(md)
    assert chunk.search_text == "Hello World\nbody content here"


def test_snippet_truncates_long_bodies() -> None:
    long_body = "x" * 3000
    md = f"# T\n## S\n\n{long_body}"
    [chunk] = chunk_text(md)
    snippet = chunk.to_snippet(max_chars=500)
    assert len(snippet) <= 501  # +1 for the ellipsis
    assert snippet.endswith("…")
