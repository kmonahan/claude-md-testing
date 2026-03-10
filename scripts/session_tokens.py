#!/usr/bin/env python3
"""
Count tokens used across all JSONL files for a given Claude session ID.

Usage: python session_tokens.py <session-id>
"""

import json
import sys
from pathlib import Path


PROJECTS_DIR = Path.home() / ".claude" / "projects"


def find_session_files(session_id: str) -> list[Path]:
    """Find all JSONL files matching the session ID (by filename or parent dir)."""
    matches = []
    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        # Match by filename: <session-id>.jsonl
        if jsonl.stem == session_id:
            matches.append(jsonl)
        # Match by parent directory: <session-id>/<anything>.jsonl
        elif session_id in jsonl.parts:
            matches.append(jsonl)
    return sorted(matches)


def sum_tokens(path: Path) -> dict:
    """Sum all token fields from usage objects in a JSONL file."""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = None
            # Direct usage field on the entry
            if "usage" in entry:
                usage = entry["usage"]
            # Nested inside message (assistant entries)
            elif isinstance(entry.get("message"), dict):
                usage = entry["message"].get("usage")
            if not isinstance(usage, dict):
                continue
            for key in totals:
                totals[key] += usage.get(key, 0)
    return totals


def format_row(label: str, counts: dict) -> str:
    total = sum(counts.values())
    return (
        f"  {label}\n"
        f"    Input:              {counts['input_tokens']:>12,}\n"
        f"    Output:             {counts['output_tokens']:>12,}\n"
        f"    Cache creation:     {counts['cache_creation_input_tokens']:>12,}\n"
        f"    Cache read:         {counts['cache_read_input_tokens']:>12,}\n"
        f"    Total:              {total:>12,}\n"
    )


def add_dicts(a: dict, b: dict) -> dict:
    return {k: a[k] + b[k] for k in a}


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <session-id>")
        sys.exit(1)

    session_id = sys.argv[1]
    files = find_session_files(session_id)

    if not files:
        print(f"No JSONL files found for session ID: {session_id}")
        print(f"Searched in: {PROJECTS_DIR}")
        sys.exit(1)

    print(f"Session: {session_id}")
    print(f"Files found: {len(files)}\n")

    grand_total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    for path in files:
        counts = sum_tokens(path)
        grand_total = add_dicts(grand_total, counts)
        # Show path relative to projects dir for brevity
        try:
            label = str(path.relative_to(PROJECTS_DIR))
        except ValueError:
            label = str(path)
        print(format_row(label, counts))

    if len(files) > 1:
        print("-" * 50)
        print(format_row("GRAND TOTAL", grand_total))
    else:
        print(f"  Grand total: {sum(grand_total.values()):,}")


if __name__ == "__main__":
    main()
