"""Helpers for patching :mod:`tqdm` defaults."""
from __future__ import annotations

import sys
from functools import wraps
from typing import Callable, Optional

try:
    import tqdm.auto as _tqdm_auto
except Exception:  # pragma: no cover - tqdm should always be available
    _tqdm_auto = None  # type: ignore[assignment]

_ORIGINAL_TQDM: Optional[Callable[..., object]] = None
_PATCH_APPLIED = False


def _determine_disable_default() -> bool:
    """Return whether progress output should be disabled by default."""
    try:
        return not sys.stderr.isatty()
    except Exception:
        # In environments without a stderr TTY (or when stderr is mocked),
        # suppress progress output to avoid noisy logs.
        return True


def _build_wrapper(original: Callable[..., object]) -> Callable[..., object]:
    """Wrap ``tqdm`` so ``disable`` defaults to headless-friendly behaviour."""

    @wraps(original)
    def tqdm_with_default(*args, **kwargs):
        kwargs.setdefault("disable", _determine_disable_default())
        return original(*args, **kwargs)

    return tqdm_with_default


def apply_patch(*, force: bool = False) -> None:
    """Patch :mod:`tqdm` so headless environments disable progress output.

    Parameters
    ----------
    force:
        Reapply the patch even if it was already installed. Useful for tests
        that monkeypatch the underlying implementation.
    """

    global _ORIGINAL_TQDM, _PATCH_APPLIED

    if _tqdm_auto is None:  # pragma: no cover - safeguard for optional dep
        return

    if not force and _PATCH_APPLIED:
        return

    if _ORIGINAL_TQDM is None or force:
        _ORIGINAL_TQDM = getattr(_tqdm_auto, "tqdm")

    if _ORIGINAL_TQDM is None:  # pragma: no cover - defensive
        return

    wrapper = _build_wrapper(_ORIGINAL_TQDM)

    _tqdm_auto.tqdm = wrapper  # type: ignore[assignment]

    try:
        import tqdm as tqdm_module  # Local import to honour monkeypatching
    except Exception:  # pragma: no cover - tqdm should be importable
        pass
    else:
        tqdm_module.tqdm = wrapper  # type: ignore[assignment]

    _PATCH_APPLIED = True


def ensure_headless_tqdm_defaults() -> None:
    """Ensure the tqdm patch has been applied."""

    apply_patch()
