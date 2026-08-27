"""Step 0 -- the day-one blame function, and why the deepest frame is the wrong frame.

Run:  uv run python -m sandbox.step0_naive_blame

Deliberately standalone -- nothing here imports `app`. This is the version of
`error_context.py` you would write before knowing any better, so you can watch it fail.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from types import TracebackType

# ---------------------------------------------------------------------------
# A fake request path, four layers deep -- the same shape as the real app:
#     endpoint -> service -> client -> somebody else's code
# ---------------------------------------------------------------------------


def app_endpoint(payload: str) -> object:
    """What the FastAPI route would call."""
    return chat_service(payload)


def chat_service(payload: str) -> object:
    """Business logic."""
    return llm_client(payload)


def llm_client(payload: str) -> object:
    """The last line of YOUR code before control crosses into a dependency.

    This is the line you want the log to point at.
    """
    return json.loads(payload)


# ---------------------------------------------------------------------------
# The day-one implementation: walk to the deepest frame and report it.
# ---------------------------------------------------------------------------


def naive_blame(exc: BaseException) -> str:
    """Deepest frame in the traceback. Correct, and almost never useful."""
    tb: TracebackType | None = exc.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return "<no traceback>"
    return f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}"


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def short(path: str) -> str:
    """`json/decoder.py` -- enough to identify, short enough to fit in a table."""
    p = Path(path)
    return f"{p.parent.name}/{p.name}"


def show_stack(exc: BaseException) -> None:
    """Print every frame of the traceback with who owns it."""
    rows = list(traceback.walk_tb(exc.__traceback__))
    mine = sum(1 for frame, _ in rows if frame.f_code.co_filename == __file__)

    print(f"\n{len(rows)} frames, {mine} of them yours. Python's order is outermost-first:\n")
    print(f"  {'#':>2}  {'where':<56}  whose")
    print(f"  {'--':>2}  {'-' * 56}  {'-' * 6}")
    for i, (frame, lineno) in enumerate(rows):
        code = frame.f_code
        owner = "YOURS" if code.co_filename == __file__ else "theirs"
        where = f"{short(code.co_filename)}:{lineno} in {code.co_qualname}"
        print(f"  {i:>2}  {where:<56}  {owner}")


def deepest_frame_of_mine(exc: BaseException) -> str:
    """The whole point of `error_context.py`, in three lines.

    Filter the stack to frames you own, take the deepest. Everything else in the real
    module is the edge cases that make this correct and cheap.
    """
    ours = [(f, n) for f, n in traceback.walk_tb(exc.__traceback__) if f.f_code.co_filename == __file__]
    if not ours:
        return "<nothing of yours in this stack>"
    frame, lineno = ours[-1]
    return f"{short(frame.f_code.co_filename)}:{lineno} in {frame.f_code.co_qualname}"


def main() -> None:
    """Trigger the failure, then compare the two answers."""
    try:
        app_endpoint('{"model": "gpt-5.4-mini", }')  # trailing comma -- invalid JSON
    except json.JSONDecodeError as exc:
        show_stack(exc)
        print("\n" + "=" * 74)
        print(f"  naive_blame()      ->  {naive_blame(exc)}")
        print("                         true, and useless: that file is not yours")
        print(f"\n  what you wanted    ->  {deepest_frame_of_mine(exc)}")
        print("=" * 74)
        print("\nAnd here is what Python prints today -- count the lines before the useful one:\n")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
