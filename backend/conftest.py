"""Root conftest, imported by pytest before any test module.

DATABASE_URL has no default in Settings so that a misconfigured deployment
fails at boot. The test suite builds its own in-memory engines, so it only
needs the variable to exist before app.config is imported.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
