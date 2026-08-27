"""
Only job of this module is to turn a traceback into "go read this line."
Nothing else in the file matters. Every design decision below is downstream of that one sentence.

--- Stack introspection: turning a traceback into the answer to "where in *my* code did this fail?".

Separate from `exceptions.py` (which owns the failure *taxonomy*) and `exception_handlers.py` (which
owns logging and the HTTP response) because this is a third, independent job: reading frame objects
and deciding which one a human should look at. It has no knowledge of HTTP, of log formats, or of any
particular exception type -- it takes an exception or a stack level and returns plain data (SRP).

**Why this file exists at all.** A production stack for one agent request is 40+ frames deep:
uvicorn -> starlette -> fastapi -> our endpoint -> our service -> langchain -> httpx -> ssl. Python's
own traceback puts the *innermost* frame last, which is almost always somebody else's code, and the
frame you actually need is buried in the middle. Three things fix that, and this module produces all
three:

  * `capture_origin()`  -- where the exception was *constructed* (the `raise` site)
  * `blame_frame()`     -- the deepest frame that belongs to **us**, i.e. the line to go read
  * `first_party_frames()` -- the path the failure took through our own layers, innermost first

The full traceback is still logged (see `exception_handlers.py`); these are the *indexable* summary
fields, so "every failure in `LLMService.invoke`" is a log query rather than an afternoon of grepping.

Here's what you'd write on day one:

def blame(exc):
    tb = exc.__traceback__
    while tb.tb_next:          # walk to the deepest frame
        tb = tb.tb_next
    return f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}"

Run it on a real LLM timeout and you get:

/home/app/.venv/lib/python3.12/site-packages/httpx/_transports/default.py:101

That is true and useless. The deepest frame is almost never yours — your code called httpx which called ssl which raised. A production agent request is 40+ frames: uvicorn → starlette → fastapi → your endpoint → your service → langchain → httpx → ssl. Yours are the four in the middle.

Everything in this file exists to turn that line into:

app/services/llm.py:42 in LLMService.invoke

The whole module is one idea: filter the stack down to frames you own, then take the deepest one. The other 250 lines are the edge cases that make that filter correct and cheap.


"""

from __future__ import (
    annotations,  # don't try to understand my type labels right now, just write them down and move on.
)

import sys
import traceback
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import FrameType, TracebackType
from typing import Any

# app/core/error_context.py -> app/core -> app -> <project root>. Same derivation as config.py, for
# the same reason: it must not depend on the working directory uvicorn or pytest was launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VENV_DIR = PROJECT_ROOT / ".venv"

# How many of our own frames to keep. First-party frames are few by nature (endpoint -> service ->
# client); the cap only guards against runaway recursion producing a log line thousands of frames long.
_MAX_FIRST_PARTY_FRAMES = 15

# How far to follow `__cause__` / `__context__`. Chains longer than this are pathological, and each
# link costs another full frame walk.
_MAX_CHAIN_DEPTH = 5


@lru_cache(maxsize=2048)
def _classify(filename: str) -> tuple[str, bool]:
    """`(display path, is_first_party)` for one source filename. Both answers, one resolution.

    🚨 **The cache is not an optimisation, it is load-bearing.** `Path.resolve()` is a filesystem
    syscall, and this used to be called three times per frame (display path, first-party flag, and
    the flag again from inside the display path) on every frame of every walk -- while `describe()`
    walked each traceback twice. Together those cost ~40 ms on a 22-frame traceback. Bypassing this
    decorator alone (see `scripts/bench_logging.py`'s sibling, `scripts/bench_error_context.py`)
    still shows ~6,700 us against ~26 us cached: a ~250x difference on the error path.

    Errors arrive in bursts -- a provider outage produces thousands in a row -- so that cost landed
    exactly when the service was already degraded. `co_filename` takes one distinct value per source
    file, so a process sees a few hundred keys at most and every walk after the first is pure
    dict lookups. Paths do not change within a process, so there is nothing to invalidate.

    Synthetic frames -- `<string>`, `<stdin>`, `<listcomp>`, `<frozen importlib._bootstrap>` -- are
    CPython's convention for "no file", and they must be rejected **before** `resolve()`: on a
    relative or synthetic name `resolve()` silently anchors to the current working directory, which
    is usually this project root, so a synthetic frame would otherwise be reported as our own code.
    """
    if not filename or filename.startswith("<"):
        return filename, False
    try:
        resolved = Path(filename).resolve()
    except (OSError, ValueError):
        # A filename containing a NUL byte or otherwise invalid for this platform.
        return filename, False

    if _VENV_DIR not in resolved.parents and (PROJECT_ROOT == resolved or PROJECT_ROOT in resolved.parents):
        return resolved.relative_to(PROJECT_ROOT).as_posix(), True
    # Dependency frames: `httpx/_client.py` beats both a bare filename (ambiguous across packages)
    # and the full site-packages path (80 characters of build-machine layout).
    return f"{resolved.parent.name}/{resolved.name}", False


def is_first_party(filename: str) -> bool:
    """True when a path belongs to this project rather than to a dependency or the stdlib.

    The boundary is the project root minus `.venv`, not the `app/` package: a failure raised from
    `tests/` or `scripts/` is still *our* code and still the frame worth reporting.
    """
    return _classify(filename)[1]


def _display_path(filename: str) -> str:
    """A path short enough to read in a log line but specific enough to open in an editor."""
    return _classify(filename)[0]


@dataclass(frozen=True, slots=True)
class CodeOrigin:
    """One point in the codebase: the unit every diagnostic field in this project is built from.

    Frozen because it is a fact about a moment that has already happened -- nothing downstream has
    any business editing it.
    """

    file: str
    line: int
    function: str
    module: str
    first_party: bool

    @property
    def location(self) -> str:
        """`app/services/llm.py:42 in LLMService.invoke` -- one greppable string for a log line."""
        return f"{self.file}:{self.line} in {self.function}"

    def as_dict(self) -> dict[str, Any]:
        """Flat form for structured logging. Flat, not nested, so an aggregator can facet on it."""
        return {
            "file": self.file,
            "line": self.line,
            "function": self.function,
            "module": self.module,
            "location": self.location,
        }


def _origin_from_frame(frame: FrameType, lineno: int | None = None) -> CodeOrigin:
    """Build a `CodeOrigin` from a live frame.

    `co_qualname` (Python 3.11+) is what makes the *class* visible: it yields
    `LLMService.invoke` where `co_name` would only give `invoke`, and "which class" is half of
    "where is this failing" in a codebase with several implementations of one Protocol.
    """
    code = frame.f_code
    return CodeOrigin(
        file=_display_path(code.co_filename),
        line=lineno if lineno is not None else frame.f_lineno,
        function=code.co_qualname,
        module=frame.f_globals.get("__name__", "<unknown>"),
        first_party=is_first_party(code.co_filename),
    )


def capture_origin(skip_instance: object | None = None) -> CodeOrigin | None:
    """Where the caller is, skipping this module and any constructor frame of `skip_instance`.

    Used by `AppException.__init__` to record the `raise` site. The raise site is **not at a fixed
    stack depth**, so counting stack levels cannot work: a subclass that defines its own `__init__`
    and calls `super().__init__()` adds a frame, and a two-level hierarchy adds two.

    Skipping by *filename* does not work either -- it fails exactly when the subclass is defined in
    the same file as the code that raises, which is the common case for a locally-defined error.
    So the rule is identity-based: skip every frame whose `self` **is** the object being
    constructed. That walks off the end of the constructor chain however deep it goes, in whatever
    files, and lands on the first frame that is genuinely somebody *calling* the constructor.

    Returns `None` rather than raising if the stack cannot be read -- a diagnostic aid must never be
    the reason a request fails.
    """
    try:
        frame: FrameType | None = sys._getframe(1)
    except (ValueError, AttributeError):  # pragma: no cover - CPython always provides this
        return None
    while frame is not None:
        if not _is_internal_frame(frame, skip_instance):
            return _origin_from_frame(frame)
        frame = frame.f_back
    return None


def _is_internal_frame(frame: FrameType, skip_instance: object | None) -> bool:
    """True for frames that are plumbing rather than the caller we are looking for."""
    # Plain string comparison, no `resolve()`: `__file__` is absolute since Python 3.9, and a
    # function defined in this module always reports exactly that string as its `co_filename`. No
    # path normalisation means no exception to guard against.
    if frame.f_code.co_filename == __file__:
        return True
    if skip_instance is None:
        return False
    # `f_locals.get("self") is skip_instance` identifies a constructor (or any method) frame of the
    # very object being built -- identity, not name matching, so it cannot be fooled by a subclass
    # that renames things or by an unrelated local called `self`.
    return frame.f_locals.get("self") is skip_instance


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """`exc` plus the exceptions it was raised from, outermost first, bounded by `_MAX_CHAIN_DEPTH`.

    Follows `__cause__` (`raise X from e`) preferentially and falls back to `__context__` (an error
    raised while handling another). `__suppress_context__` is honoured, because `from None` is an
    explicit statement that the earlier error is not relevant.
    """
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(chain) < _MAX_CHAIN_DEPTH and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        if current.__cause__ is not None:
            current = current.__cause__
        elif not current.__suppress_context__:
            current = current.__context__
        else:
            current = None
    return chain


def _walk(tb: TracebackType | None) -> list[CodeOrigin]:
    """Every frame of one traceback, outermost first (Python's own order)."""
    return [_origin_from_frame(frame, lineno) for frame, lineno in traceback.walk_tb(tb)]


def first_party_frames(exc: BaseException) -> list[CodeOrigin]:
    """Our own frames across the whole exception chain, **innermost first**.

    Innermost first is the reverse of Python's traceback order, and it is deliberate: the first entry
    is the line that broke, and each following entry is the caller that led there. That reads as a
    story ("failed in `invoke`, called from `chat`, called from the endpoint") and puts the most
    useful frame where the eye lands, instead of after 30 lines of framework.
    """
    ours: list[CodeOrigin] = []
    for link in _exception_chain(exc):
        for origin in reversed(_walk(link.__traceback__)):
            if origin.first_party and len(ours) < _MAX_FIRST_PARTY_FRAMES:
                ours.append(origin)
    return ours


def _blame_from(ours: list[CodeOrigin], chain: list[BaseException]) -> CodeOrigin | None:
    """Pick the blame frame from an already-computed first-party list, or fall back.

    Takes the list rather than recomputing it, so `describe()` walks each traceback once instead of
    twice. See `_classify` for why a second walk is not free.
    """
    if ours:
        return ours[0]
    # Nothing of ours in the stack: a failure entirely inside a dependency still needs *a* location,
    # even if it is `httpx/_client.py`.
    for link in chain:
        frames = _walk(link.__traceback__)
        if frames:
            return frames[-1]
    return None


def blame_frame(exc: BaseException) -> CodeOrigin | None:
    """The single frame to go and read: the deepest first-party frame in the chain.

    Returns `None` only for an exception with no traceback at all (one constructed but never raised).
    """
    return _blame_from(first_party_frames(exc), _exception_chain(exc))


def describe(exc: BaseException) -> dict[str, Any]:
    """The full diagnostic bundle for one exception, ready to splat into a log call.

    Deliberately *only* the summary/index fields. The complete formatted traceback is attached
    separately by the caller via `exc_info`, so this dict stays small enough to keep in a log
    aggregator's indexed fields while the traceback lives in the message body.
    """
    chain = _exception_chain(exc)  # builld what caused what chain?
    # One walk, reused for both the blame frame and the app_traceback list.
    ours = first_party_frames(exc)
    blame = _blame_from(ours, chain)
    described: dict[str, Any] = {
        "exception_type": type(exc).__qualname__,
        "exception_module": type(exc).__module__,
        "exception_message": str(exc),
    }
    if blame is not None:
        described["blame"] = blame.as_dict()
        described["failed_at"] = blame.location
    if ours:
        described["app_traceback"] = [origin.location for origin in ours]
    if len(chain) > 1:
        described["caused_by"] = [f"{type(link).__qualname__}: {link}" for link in chain[1:]]
    return described
