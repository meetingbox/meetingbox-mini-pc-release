"""Shared test setup.

Several test modules stub `sys.modules["kivy"]` with a minimal fake so they can
import device code without the real toolkit. `conftest.py` is imported before
any test module, so importing the real Kivy here first means those stubs become
no-ops (they all use `setdefault`) and tests that need genuine Kivy behaviour —
e.g. ScreenManager lifecycle dispatch — get it regardless of collection order.

If Kivy is not installed (CI without the toolkit) this is a no-op and the
Kivy-dependent tests skip themselves.
"""

import os

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "error")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

try:  # pragma: no cover - depends on environment
    import kivy.uix.screenmanager  # noqa: F401
except Exception:  # pragma: no cover
    pass
