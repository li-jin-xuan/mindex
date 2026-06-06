# MIndex

**纯文本记忆系统 · 标准库零依赖 · 可版本控制 · Claude Code 原生**

[![CI](https://github.com/li-jin-xuan/mindex/actions/workflows/ci.yml/badge.svg)](https://github.com/li-jin-xuan/mindex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

MIndex 是一个面向 Claude Code 的长期记忆目录。它把经过筛选的稳定事实、偏好和项目决策保存在 Markdown 中，用脚本维护可召回索引。

它不会把全部对话自动保存为“记忆”。完整聊天记录噪声大、易泄露敏感信息，也会持续占用上下文；MIndex 只保留未来仍有价值的信息。

Claude Code 已提供按仓库工作的 Auto Memory。MIndex 不替代它，而是补充一个可审计、可版本控制、可跨项目共享的结构化事实层：

- Auto Memory：Claude 自动积累的仓库经验和使用模式
- MIndex：用户确认的长期偏好、跨项目事实、项目决策和技术结论

## 核心设计

```
INDEX.md          ← 自动生成的主索引（常驻上下文）
preferences/      ← 偏好和规则（自动加载）
projects/         ← 项目详情（按需加载）
tech/             ← 技术参考（按需加载）
daily/            ← 每日日志
archive/          ← 已归档内容
tools/            ← 维护脚本
```

## 快速开始

```bash
git clone https://github.com/li-jin-xuan/mindex.git
cd mindex

# 接入用户级 Claude Code 记忆（对所有项目生效）
python3 tools/install.py
python3 tools/install.py --check

# 查看当前状态
cat INDEX.md

# 修改记忆文件后重建索引
python3 tools/generate_index.py

# 检查系统完整性
python3 tools/verify.py
```

## 工作流

1. 编辑 `.md` 文件（要求 YAML frontmatter）
2. 运行 `python3 tools/generate_index.py` 更新索引
3. 运行 `python3 tools/verify.py`
4. 审查差异后提交到 Git

## 文件规范

每个 `.md` 文件应包含 frontmatter：

```
---
title: 条目名称
status: active | pending | archived | completed
updated: YYYY-MM-DD
---
```

## 系统要求

- Python 3.10+
- Git
- Linux / macOS / Windows

## 开发与验证

```bash
make check
```

Windows PowerShell：

```powershell
python -m unittest discover -s tests -v
python tools/verify.py
```

## 许可证

[MIT](LICENSE)
