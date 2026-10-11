from __future__ import annotations
"""
Guards the single most dangerous silent bug class in this repo:
DB_PATH computed relative to __file__ after module moves (P1.1 regression:
backend/db/base.py pointed at backend/data/ instead of data/).

Uses stdlib unittest, no DB writes.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import DB_PATH
from backend.db.base import DB_PATH as BASE_DB_PATH


class TestDbPath(unittest.TestCase):
    def test_db_path_is_repo_data(self):
        expected = os.path.join(PROJECT_ROOT, "data", "questions.db")
        self.assertEqual(
            os.path.normpath(os.path.abspath(DB_PATH)),
            os.path.normpath(os.path.abspath(expected)),
            f"DB_PATH sai: {DB_PATH} (muon {expected})",
        )

    def test_db_path_not_under_backend_dir(self):
        self.assertNotIn(
            os.sep + "backend" + os.sep,
            os.path.abspath(DB_PATH),
            f"DB_PATH nam trong backend/: {DB_PATH}",
        )

    def test_base_and_shim_agree(self):
        self.assertEqual(
            os.path.abspath(BASE_DB_PATH), os.path.abspath(DB_PATH)
        )


if __name__ == "__main__":
    unittest.main()
