"""Does error_context.py produce the same strings on Windows and Linux?

Run:  uv run python sandbox/check_os_paths.py
"""

import os
import sys
from pathlib import Path

import structlog

from app.core.error_context import PROJECT_ROOT, _classify, is_first_party

print(f"platform={sys.platform}  os.sep={os.sep!r}  PROJECT_ROOT={PROJECT_ROOT}\n")

app_file = str(PROJECT_ROOT / "app" / "core" / "config.py")
cases = {
    "our own file": app_file,
    "dependency in .venv": structlog.__file__,
    "stdlib": Path(os.__file__).as_posix(),
    "synthetic <string>": "<string>",
    "synthetic <frozen ...>": "<frozen importlib._bootstrap>",
    "relative path": "app/core/config.py",
    "backslash-separated": app_file.replace("/", "\\"),
    "UPPERCASED (win case-insensitivity)": app_file.upper(),
}

print(f"  {'input':<38}  {'display':<34}  first_party")
print(f"  {'-' * 38}  {'-' * 34}  {'-' * 11}")
for label, value in cases.items():
    display, first_party = _classify(value)
    print(f"  {label:<38}  {display:<34}  {first_party}")

print("\nno backslash may survive into a display path:")
leaks = [d for d, _ in (_classify(v) for v in cases.values()) if "\\" in d]
print(f"  leaked = {leaks or 'none'}")

print("\n.venv sits INSIDE the project root, so the venv check is what saves us:")
print(f"  structlog under PROJECT_ROOT?  {PROJECT_ROOT in Path(structlog.__file__).resolve().parents}")
print(f"  is_first_party(structlog)?     {is_first_party(structlog.__file__)}")
