# sandbox/

Throwaway scripts for seeing a concept fail before building the real thing.
Nothing here is imported by `app/`. Break it freely.

```bash
uv run python -m sandbox.step0_naive_blame
```

Use `-m`, not a file path: `python -m` puts the project root on `sys.path`, which is
what lets a sandbox script do `import app...`. Plain `python sandbox/x.py` does not
(the project is `package = false`, so `app` is never installed -- pytest gets there
via `pythonpath = ["."]`).

| Script | Teaches | Real module |
|---|---|---|
| `step0_naive_blame.py` | the deepest frame is almost never yours | `app/core/error_context.py` |
| `check_os_paths.py` | display paths stay `/`-separated on Windows | `app/core/error_context.py` |

Excluded from `mypy` and from ruff's `ERA`/`S`/`T201` rules (see `pyproject.toml`) so a
half-finished experiment never fails the gate. Not gitignored -- keep the ones worth
rereading, delete the rest.
