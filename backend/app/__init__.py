from __future__ import annotations

import warnings

# python-multipart 0.0.32 deprecates legacy ``import multipart`` used by
# starlette 0.38.x (via fastapi 0.115.0). CI uses PYTHONWARNINGS=error for
# create_app().openapi(); ignore only this upstream deprecation until starlette
# switches to ``import python_multipart``.
warnings.filterwarnings(
    "ignore",
    message=r"Please use `import python_multipart` instead\.",
    category=PendingDeprecationWarning,
)

from .main import app, application, create_app  # noqa: E402

__all__ = ["app", "application", "create_app"]
