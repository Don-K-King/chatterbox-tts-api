"""Runtime patches for third-party dependencies."""

from .tqdm_patch import ensure_headless_tqdm_defaults

__all__ = ["ensure_headless_tqdm_defaults"]
