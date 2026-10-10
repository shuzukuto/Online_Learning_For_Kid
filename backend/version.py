"""EduQuest Pro — Single source of truth for app versions.

Mọi nơi khác (backend FastAPI, frontend badges, cache-buster, docs, tests)
phải đọc từ đây thay vì hard-code số version rời rạc.
"""
from __future__ import annotations

APP_VERSION = "v1.0.43"
APP_VERSION_NUMBER = "1.0.43"
CACHE_BUSTER = "1.0.48"
EXT_VERSION = "v1.3.18"
EXT_VERSION_NUMBER = "1.3.18"
