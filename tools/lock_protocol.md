---
title: 写入锁协议
status: active
updated: 2026-06-06
---

# 写入锁协议

## 为什么需要锁
多 agent 同时修改 INDEX.md 或记忆文件时，后写入的会覆盖先写入的改动（lost update）。锁机制确保同一时间只有一个写入者。

## 锁文件位置
`.memory.lock`（该文件被 .gitignore）

## 获取锁（Python）
```python
import os, fcntl
LOCK = ".memory.lock"
fd = os.open(LOCK, os.O_CREAT | os.O_RDWR, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)  # 阻塞直到获得锁
# ... 写入操作 ...
os.close(fd)  # 锁自动释放
```

## 获取锁（Shell）
```bash
exec 200>.memory.lock
flock -x 200  # 阻塞直到获得锁
# ... 写入操作 ...
# 退出作用域时锁自动释放
```

Windows 使用 Python 标准库 `msvcrt.locking`，统一通过
`tools/mindex_core.py` 的 `memory_lock()` 调用。

## 规则
1. 读取不需要锁
2. 任何写入操作前先获取锁
3. 操作完成后尽快释放
4. 锁文件是持久 inode；存在不代表锁被占用，禁止删除它
5. 判断锁状态必须尝试 `flock(..., LOCK_NB)`，不能依赖 PID 文本
6. 不要长时间持有锁（超过10秒）

## 当前使用锁的工具
- `tools/generate_index.py`
- `tools/verify.py`
