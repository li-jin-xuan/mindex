#!/usr/bin/env python3
"""Install MIndex as a user-level Claude Code memory import."""

from __future__ import annotations

import argparse
from pathlib import Path

from mindex_core import atomic_write, configure_utf8_output


ROOT = Path(__file__).resolve().parent.parent
BEGIN = "<!-- mindex:begin -->"
END = "<!-- mindex:end -->"


def managed_block(root: Path = ROOT) -> str:
    return f"{BEGIN}\n# MIndex global memory\n@{(root / 'CLAUDE.md').as_posix()}\n{END}"


def replace_block(content: str, block: str | None) -> str:
    start = content.find(BEGIN)
    end = content.find(END)
    if (start == -1) != (end == -1) or (start != -1 and end < start):
        raise ValueError("检测到损坏的 MIndex 管理块，请先检查目标 CLAUDE.md")
    if start != -1:
        end += len(END)
        content = content[:start].rstrip() + content[end:].lstrip("\n")
    if block:
        return (content.rstrip() + "\n\n" + block + "\n").lstrip("\n")
    return content.rstrip() + ("\n" if content.strip() else "")


def main() -> int:
    configure_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查是否正确安装")
    parser.add_argument("--uninstall", action="store_true", help="删除 MIndex 管理块")
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude" / "CLAUDE.md")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    content = target.read_text(encoding="utf-8") if target.exists() else ""
    block = managed_block()

    if args.check:
        if block in content:
            print(f"MIndex 已安装: {target}")
            return 0
        print(f"MIndex 未安装或路径已变化: {target}")
        return 1

    try:
        updated = replace_block(content, None if args.uninstall else block)
    except ValueError as exc:
        print(f"安装失败: {exc}")
        return 1
    atomic_write(target, updated)
    action = "已卸载" if args.uninstall else "已安装"
    print(f"MIndex {action}: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
