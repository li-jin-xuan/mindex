# Contributing

## Development

MIndex requires Python 3.10 or newer and has no third-party runtime
dependencies.

```bash
python3 -m unittest discover -s tests -v
python3 tools/generate_index.py
python3 tools/verify.py
```

## Pull requests

1. Keep changes focused and preserve the plain-text architecture.
2. Add tests for behavior changes.
3. Do not commit credentials, private memories, `.memory.lock`, caches, or
   generated temporary files.
4. Regenerate `INDEX.md` when indexed Markdown files change.
