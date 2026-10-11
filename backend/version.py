"""EduQuest Pro — Single source of truth for app versions.

Mọi nơi khác (backend FastAPI, frontend badges, cache-buster, docs, tests)
phải đọc từ đây thay vì hard-code số version rời rạc.
"""
from __future__ import annotations

APP_VERSION = "v1.0.51"
APP_VERSION_NUMBER = "1.0.51"
CACHE_BUSTER = "1.0.56"
EXT_VERSION = "v1.3.18"
EXT_VERSION_NUMBER = "1.3.18"
