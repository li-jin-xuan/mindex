#!/usr/bin/env python3
"""Validate memory files and confirm INDEX.md is current."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from mindex_core import discover, memory_lock, render_index, validate


BASE = Path(__file__).resolve().parent.parent
GENERATED_LINE = re.compile(r"^> 生成时间: .+$", re.MULTILINE)


def normalize_generated_time(text: str) -> str:
    return GENERATED_LINE.sub("> 生成时间: <ignored>", text)


def main() -> int:
    errors: list[str] = []
    with memory_lock(BASE):
        entries, warnings = discover(BASE)
        errors.extend(warnings)
        errors.extend(validate(entries))

        index_path = BASE / "INDEX.md"
        if not index_path.is_file():
            errors.append("INDEX.md 不存在")
        else:
            actual = index_path.read_text(encoding="utf-8")
            expected = render_index(entries, datetime.now().astimezone())
            if normalize_generated_time(actual) != normalize_generated_time(expected):
                errors.append("INDEX.md 已过期，请运行 python3 tools/generate_index.py")

    if errors:
        print("一致性检查失败：")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"一致性检查通过（{len(entries)} 条记忆）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
