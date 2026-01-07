from __future__ import annotations

import importlib
import os
from typing import Any, Callable


def _import_attr(module_path: str, attr_name: str) -> Any:
    mod = importlib.import_module(module_path)
    return getattr(mod, attr_name)


def load_fastapi_app():
    """
    Loads FastAPI app instance.

    Resolution order:
      1) FASTAPI_APP env var: "module:attr" (e.g. "app.main:app")
      2) common defaults
    """
    candidates = []

    env = os.getenv("FASTAPI_APP", "").strip()
    if env:
        candidates.append(env)

    # common locations (adjust if your project differs)
    candidates += [
        "app.main:app",
        "main:app",
        "src.main:app",
    ]

    errors: list[str] = []
    for c in candidates:
        try:
            module_path, attr_name = c.split(":", 1)
            app = _import_attr(module_path, attr_name)
            return app
        except Exception as e:  # noqa: BLE001 (PoC: show root cause)
            errors.append(f"- {c}: {type(e).__name__}: {e}")

    msg = (
        "Failed to import FastAPI app.\n"
        "Set env FASTAPI_APP like: FASTAPI_APP=app.main:app\n"
        "Tried:\n" + "\n".join(errors)
    )
    raise RuntimeError(msg)
