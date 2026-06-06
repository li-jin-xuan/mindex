#!/usr/bin/env python3
"""Shared indexing, validation, and locking primitives for MIndex."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

if os.name == "nt":
    import msvcrt
else:
    import fcntl


CATEGORIES = (
    ("projects", "当前项目"),
    ("preferences", "偏好"),
    ("tech", "技术"),
    ("archive", "归档"),
    ("daily", "每日日志"),
    ("tools", "工具"),
)
VALID_STATUSES = {"active", "pending", "archived", "completed"}
SKIP_NAMES = {
    "claude.md",
    "contributing.md",
    "index.md",
    "readme.md",
    "security.md",
    "_template.md",
}
SENSITIVE_NAME_PARTS = {
    "auth",
    "credential",
    "credentials",
    "key",
    "keys",
    "password",
    "passwords",
    "secret",
    "secrets",
    "token",
    "tokens",
}
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


@dataclass(frozen=True)
class Entry:
    path: str
    category: str
    metadata: dict[str, str]
    body: str


def configure_utf8_output() -> None:
    """Make CLI messages portable to Windows consoles with legacy encodings."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    metadata: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata, text[match.end() :].strip()


def discover(base: Path) -> tuple[list[Entry], list[str]]:
    entries: list[Entry] = []
    warnings: list[str] = []
    category_names = {name for name, _ in CATEGORIES}

    for path in sorted(base.rglob("*.md")):
        relative = path.relative_to(base)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.name.casefold() in SKIP_NAMES:
            continue
        name_parts = set(filter(None, re.split(r"[^a-z0-9]+", path.stem.casefold())))
        if name_parts & SENSITIVE_NAME_PARTS:
            warnings.append(f"疑似敏感文件，拒绝索引: {relative.as_posix()}")
            continue
        if not relative.parts or relative.parts[0] not in category_names:
            warnings.append(f"未分类文件: {relative.as_posix()}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"无法读取 {relative.as_posix()}: {exc}")
            continue
        metadata, body = parse_frontmatter(text)
        entries.append(
            Entry(
                path=relative.as_posix(),
                category=relative.parts[0],
                metadata=metadata,
                body=body,
            )
        )
    return entries, warnings


def _escape_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\n", " ")
        .strip()
    )


def render_index(entries: list[Entry], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now().astimezone()
    grouped = {name: [] for name, _ in CATEGORIES}
    for entry in entries:
        grouped[entry.category].append(entry)

    lines = [
        "# 记忆索引",
        "",
        "> 自动生成，请勿手动修改。运行 `python3 tools/generate_index.py` 重建。",
        f"> 生成时间: {generated_at.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
    ]
    for category, heading in CATEGORIES:
        items = grouped[category]
        if not items and category not in {"projects", "preferences", "tech"}:
            continue
        lines.extend((f"## {heading}", "| 名称 | 状态 | 更新时间 | 位置 |", "|---|---|---|---|"))
        for entry in items:
            fallback = next(
                (
                    line.lstrip("# ").strip()
                    for line in entry.body.splitlines()
                    if line.strip()
                ),
                entry.path,
            )
            title = _escape_cell(entry.metadata.get("title", fallback)[:80])
            status = _escape_cell(entry.metadata.get("status", "-"))
            updated = _escape_cell(entry.metadata.get("updated", "-"))
            path = _escape_cell(entry.path)
            target = quote(entry.path, safe="/")
            lines.append(f"| {title} | {status} | {updated} | [{path}]({target}) |")
        lines.append("")
    return "\n".join(lines)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


@contextmanager
def memory_lock(base: Path, blocking: bool = True) -> Iterator[None]:
    """Acquire an OS-backed exclusive lock without unlinking the lock file."""
    lock_path = base / ".memory.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        if os.name == "nt":
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            msvcrt.locking(fd, mode, 1)
        else:
            operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            fcntl.flock(fd, operation)
        acquired = True
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        os.fsync(fd)
        yield
    finally:
        try:
            if acquired and os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            elif acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def validate(entries: list[Entry]) -> list[str]:
    errors: list[str] = []
    ids: dict[str, str] = {}

    for entry in entries:
        metadata = entry.metadata
        for field in ("title", "status", "updated"):
            if not metadata.get(field):
                errors.append(f"{entry.path}: 缺少 frontmatter 字段 {field}")
        status = metadata.get("status")
        if status and status not in VALID_STATUSES:
            errors.append(f"{entry.path}: 无效状态 {status!r}")
        updated = metadata.get("updated")
        if updated:
            try:
                date.fromisoformat(updated)
            except ValueError:
                errors.append(f"{entry.path}: 无效日期 {updated!r}")
        entry_id = metadata.get("id")
        if entry_id:
            if entry_id in ids:
                errors.append(f"{entry.path}: id {entry_id!r} 与 {ids[entry_id]} 重复")
            else:
                ids[entry_id] = entry.path

    for entry in entries:
        raw_dependencies = entry.metadata.get("depends_on", "").strip()
        if not raw_dependencies:
            continue
        if raw_dependencies.startswith("[") and raw_dependencies.endswith("]"):
            raw_dependencies = raw_dependencies[1:-1]
        for dependency in (item.strip().strip("\"'") for item in raw_dependencies.split(",")):
            if dependency and dependency not in ids:
                errors.append(f"{entry.path}: depends_on 引用了不存在的 id {dependency!r}")
    return errors
