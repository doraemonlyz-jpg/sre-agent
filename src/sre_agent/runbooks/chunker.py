"""
Markdown runbook chunker.

Convention:

    # Title of the runbook         ← file-level title (one)
    Some intro prose...

    ## Section title               ← one chunk per ## heading
    > service: checkout-api        ← OPTIONAL metadata block on first lines
    > tags: redis, latency, pool   ← (any number of `> key: value` lines)

    The body of the section, freeform markdown. Becomes the chunk's `body`.

    ## Another section
    ...

Each `## ` heading produces one `RunbookChunk` with:

* `title`     — the heading text
* `service`   — pulled from the `> service:` line if present
* `tags`      — pulled from `> tags:` (comma-separated)
* `body`      — the section content with the metadata lines stripped
* `path`      — relative path to the file (set by the caller)

The chunker is pure (no I/O) and trivially testable. `chunk_file()` is the
thin wrapper that reads a file from disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_META_LINE_RE = re.compile(r"^\s*>\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.+?)\s*$")
_SECTION_SPLIT_RE = re.compile(r"(?m)^##\s+")  # split on `## ` at start of line
_MAX_BODY_LEN = 2200  # keep chunks LLM-context-friendly


@dataclass
class RunbookChunk:
    """One section of a runbook."""

    path: str
    title: str
    body: str
    service: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def search_text(self) -> str:
        """Concatenated text used for embedding / keyword retrieval."""
        return f"{self.title}\n{self.body}"

    def to_snippet(self, max_chars: int = 2200) -> str:
        return self.body if len(self.body) <= max_chars else self.body[:max_chars] + "…"


def _parse_metadata(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """
    Consume leading `> key: value` lines off the front of the section.

    Returns (metadata_dict, remaining_lines).
    """
    meta: dict[str, str] = {}
    remaining = list(lines)
    while remaining:
        line = remaining[0].rstrip()
        if not line.strip():
            remaining.pop(0)
            continue
        match = _META_LINE_RE.match(line)
        if not match:
            break
        meta[match.group(1).lower()] = match.group(2)
        remaining.pop(0)
    return meta, remaining


def chunk_text(text: str, *, path: str = "<inline>") -> list[RunbookChunk]:
    """Pure chunker — split a markdown blob into RunbookChunk objects."""
    # Drop the file-level "# Title" block before slicing on `## ` so we don't
    # produce a phantom first chunk.
    parts = _SECTION_SPLIT_RE.split(text)
    if not parts:
        return []
    # The first element is everything BEFORE the first `## ` — typically the
    # `# Title` + intro. We ignore it; it's not a retrievable chunk.
    section_blobs = parts[1:]

    chunks: list[RunbookChunk] = []
    for blob in section_blobs:
        lines = blob.splitlines()
        if not lines:
            continue
        # The blob starts with the heading text (no `## ` because the regex ate it).
        heading = lines[0].strip()
        rest = lines[1:]
        meta, body_lines = _parse_metadata(rest)
        body = "\n".join(body_lines).strip()
        if len(body) > _MAX_BODY_LEN:
            body = body[:_MAX_BODY_LEN].rstrip() + "…"
        tags_raw = meta.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        chunks.append(
            RunbookChunk(
                path=path,
                title=heading,
                body=body,
                service=meta.get("service") or None,
                tags=tags,
            )
        )
    return chunks


def chunk_file(path: Path, *, root: Path | None = None) -> list[RunbookChunk]:
    """Read a markdown file and chunk it. `root` is used to compute relative paths."""
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(root)) if root else str(path)
    return chunk_text(text, path=rel)
