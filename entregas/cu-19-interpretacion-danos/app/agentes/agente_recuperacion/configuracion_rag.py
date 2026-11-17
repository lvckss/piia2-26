"""Load local configuration only when execution is explicitly requested."""

import os
from pathlib import Path
import shlex

CASE = Path(__file__).resolve().parents[3]


def load_environment():
    for path in (CASE / ".env", CASE / "app/.env"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip().removeprefix("export ")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values = shlex.split(value, comments=True)
            os.environ.setdefault(key.strip(), " ".join(values))
