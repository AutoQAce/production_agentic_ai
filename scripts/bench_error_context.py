"""Benchmark the error-diagnostic path. Lives inside the project so its frames are first-party.

uv run python scripts/bench_error_context.py
"""

from __future__ import annotations

import timeit

from app.core import error_context
from app.core.error_context import _MAX_FIRST_PARTY_FRAMES, _classify, describe, first_party_frames
from app.core.exceptions import ConfigurationError


def _nested(depth: int) -> None:
    """Raise from `depth` frames down, all of them first-party."""
    if depth == 0:
        raise ValueError("bottom")
    _nested(depth - 1)


def _held(depth: int) -> BaseException:
    try:
        _nested(depth)
    except ValueError as exc:
        return exc
    raise AssertionError("unreachable")


def _chained() -> BaseException:
    try:
        try:
            _nested(5)
        except ValueError as root:
            raise ConfigurationError("wrapped") from root
    except ConfigurationError as exc:
        return exc
    raise AssertionError("unreachable")


def _micros(fn: object, number: int) -> float:
    return timeit.timeit(fn, number=number) / number * 1e6  # type: ignore[arg-type]


def main() -> None:
    print("=" * 72)
    print("Path classification cache (the load-bearing one)")
    print("=" * 72)
    _classify.cache_clear()
    cold = _micros(lambda: _classify(__file__), 1)
    warm = _micros(lambda: _classify(__file__), 200_000)
    print(f"  cold (one Path.resolve syscall) : {cold:9.2f} us")
    print(f"  warm (dict lookup)              : {warm:9.4f} us   -> {cold / warm:,.0f}x")
    print(f"  cache after a full run          : {_classify.cache_info()}")

    print()
    print("=" * 72)
    print("describe() -- the whole diagnostic bundle, per error")
    print("=" * 72)
    for depth in (3, 20, 60):
        exc = _held(depth)
        frames = len(first_party_frames(exc))
        cost = _micros(lambda e=exc: describe(e), 5000)
        print(f"  {depth + 2:3d}-frame traceback ({frames:2d} first-party kept): {cost:8.2f} us")
    chained = _chained()
    print(f"  2-link cause chain                          : {_micros(lambda: describe(chained), 5000):8.2f} us")

    print()
    print("=" * 72)
    print("What the cache is worth: same describe(), decorator bypassed")
    print("=" * 72)
    exc = _held(20)
    warm = _micros(lambda: describe(exc), 2000)

    # `__wrapped__` is the undecorated function. Swapping the module global makes every caller
    # (is_first_party / _display_path) pay a real Path.resolve() per frame, as the original did.
    error_context._classify = _classify.__wrapped__  # type: ignore[attr-defined]
    try:
        cold = _micros(lambda: describe(exc), 200)
    finally:
        error_context._classify = _classify
    print(f"  describe(), cached    : {warm:9.2f} us")
    print(f"  describe(), uncached  : {cold:9.2f} us   -> {cold / warm:,.0f}x")
    print("  NOTE: the pre-fix code was slower still (~40,000 us on this traceback) because it")
    print("        also walked the traceback twice. That figure is historical, not reproducible here.")

    print()
    print("=" * 72)
    print("Exception construction (capture_origin walks the stack)")
    print("=" * 72)
    print(f"  ConfigurationError('x') : {_micros(lambda: ConfigurationError('x'), 50_000):8.3f} us")
    print(f"  ValueError('x')         : {_micros(lambda: ValueError('x'), 50_000):8.3f} us")

    print()
    print("=" * 72)
    print("Frame cap")
    print("=" * 72)
    deep = first_party_frames(_held(60))
    print(f"  60-deep recursion -> {len(deep)} frames kept (_MAX_FIRST_PARTY_FRAMES={_MAX_FIRST_PARTY_FRAMES})")
    print(f"  innermost: {deep[0].location}")


if __name__ == "__main__":
    main()
