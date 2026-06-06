# MIndex · 记忆协议

`@path` 表示自动加载此文件到上下文。所有路径基于仓库根目录。

@INDEX.md
@preferences/style.md
@preferences/business.md

## 读取规则

1. 从 INDEX.md 定位相关文件，只加载当前任务需要的记忆。
2. 不直接编辑 INDEX.md，它是自动生成的。

## 写入过滤

写入前评估以下条件：
- 可以写入：用户明确表达的长期偏好、稳定事实、项目决策、已验证结论
- 不得写入：临时聊天、未验证推测、密钥、令牌、隐私数据、完整对话

## 写入规则

1. 根据内容类型选择目录：`projects/`（项目）、`tech/`（技术）、`preferences/`（偏好）、`daily/`（日志）、`archive/`（归档）。
2. 每条记忆应包含 YAML frontmatter（title / status / updated）。
3. 更新既有事实而非追加重复信息；冲突时保留来源和日期。
4. 写入前获取锁（见 `tools/lock_protocol.md`），写入后运行：
   `python3 tools/generate_index.py && python3 tools/verify.py`
5. 验证失败时，修正 frontmatter 或内容错误后重试；无法修复则放弃写入。

## 目录说明

| 目录 | 用途 |
|------|------|
| `projects/` | 当前活跃项目 |
| `preferences/` | 偏好和规则（自动加载） |
| `tech/` | 技术参考和架构 |
| `daily/` | 每日日志，按 YYYY-MM-DD.md 命名 |
| `archive/` | 已归档或已完成的项目 |
| `tools/` | 维护脚本 |
