import sys
import types

import pytest

from app.patches import tqdm_patch


@pytest.fixture
def reset_patch_state(monkeypatch):
    monkeypatch.setattr(tqdm_patch, "_ORIGINAL_TQDM", None, raising=False)
    monkeypatch.setattr(tqdm_patch, "_PATCH_APPLIED", False, raising=False)
    return monkeypatch


def _install_dummy_tqdm(monkeypatch, *, disable_default: bool, use_class: bool = False):
    calls = []

    if use_class:
        class FakeTqdm:
            def __init__(self, *args, **kwargs):
                calls.append(kwargs.copy())

        tqdm_impl = FakeTqdm
    else:
        def fake_tqdm(*args, **kwargs):
            calls.append(kwargs.copy())
            return []

        tqdm_impl = fake_tqdm

    dummy_module = types.SimpleNamespace(tqdm=tqdm_impl)

    monkeypatch.setattr(tqdm_patch, "_tqdm_auto", dummy_module, raising=False)
    monkeypatch.setitem(sys.modules, "tqdm", dummy_module)
    monkeypatch.setattr(tqdm_patch, "_determine_disable_default", lambda: disable_default)

    return dummy_module, calls


def test_tqdm_patch_disables_when_stderr_not_tty(reset_patch_state):
    monkeypatch = reset_patch_state
    dummy_module, calls = _install_dummy_tqdm(monkeypatch, disable_default=True)

    tqdm_patch.apply_patch(force=True)

    dummy_module.tqdm(range(3))

    assert calls[-1]["disable"] is True


def test_tqdm_patch_preserves_explicit_disable(reset_patch_state):
    monkeypatch = reset_patch_state
    dummy_module, calls = _install_dummy_tqdm(monkeypatch, disable_default=False)

    tqdm_patch.apply_patch(force=True)

    dummy_module.tqdm(range(2), disable=False)

    assert calls[-1]["disable"] is False


def test_tqdm_patch_preserves_class_behaviour(reset_patch_state):
    monkeypatch = reset_patch_state
    dummy_module, calls = _install_dummy_tqdm(monkeypatch, disable_default=True, use_class=True)

    tqdm_patch.apply_patch(force=True)

    class CustomTqdm(dummy_module.tqdm):
        pass

    CustomTqdm(range(1))

    assert calls[-1]["disable"] is True
