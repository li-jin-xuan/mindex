#!/usr/bin/env python3
"""Generate INDEX.md safely and deterministically."""

from pathlib import Path

from mindex_core import atomic_write, discover, memory_lock, render_index


BASE = Path(__file__).resolve().parent.parent


def main() -> int:
    with memory_lock(BASE):
        entries, warnings = discover(BASE)
        for warning in warnings:
            print(f"WARNING: {warning}")
        atomic_write(BASE / "INDEX.md", render_index(entries))
    print(f"INDEX.md 已生成（{len(entries)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
