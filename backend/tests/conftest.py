from __future__ import annotations

import os
import sys
from pathlib import Path

# Required before app.config / runtime import. Tests always use non-Secure cookies.
os.environ["COOKIE_SECURE"] = "false"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
