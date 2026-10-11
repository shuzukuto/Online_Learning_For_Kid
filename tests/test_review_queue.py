from __future__ import annotations
"""
Unit Tests for EduQuest Pro Spaced-Repetition Review Queue (P1.3b).
Uses stdlib unittest + temp SQLite file (never touches data/questions.db).
RED: module backend.db.review does not exist yet.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.db.review import (
    get_due_reviews,
    get_review_state,
    get_review_stats,
    record_review_results,
)

VN = timezone(timedelta(hours=7))


def _r(qid, correct, subject="math", grade=5):
    return {"question_id": qid, "correct": correct, "subject": subject, "grade": grade}


class TestReviewQueue(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_wrong_answer_not_due_immediately_but_due_next_day(self):
        record_review_results(self.db, [_r("q1", False)])
        now = datetime.now(VN)
        self.assertEqual(get_due_reviews(self.db, now=now), [])
        later = now + timedelta(days=1, minutes=1)
        due = get_due_reviews(self.db, now=later)
        self.assertEqual([d["question_id"] for d in due], ["q1"])

    def test_consecutive_correct_answers_advance_interval(self):
        record_review_results(self.db, [_r("q1", False)])
        record_review_results(self.db, [_r("q1", True)])
        record_review_results(self.db, [_r("q1", True)])
        st = get_review_state(self.db, "q1")
        self.assertIsNotNone(st)
        self.assertEqual(st["repetitions"], 2)
        self.assertEqual(st["interval_days"], 3)

    def test_wrong_answer_resets_streak(self):
        record_review_results(self.db, [_r("q1", True)])
        record_review_results(self.db, [_r("q1", True)])
        record_review_results(self.db, [_r("q1", False)])
        st = get_review_state(self.db, "q1")
        self.assertEqual(st["repetitions"], 0)
        self.assertEqual(st["interval_days"], 1)

    def test_first_correct_answer_schedules_day_one(self):
        record_review_results(self.db, [_r("q9", True)])
        st = get_review_state(self.db, "q9")
        self.assertEqual(st["repetitions"], 1)
        self.assertEqual(st["interval_days"], 1)

    def test_due_reviews_filter_by_subject_and_grade(self):
        record_review_results(self.db, [
            _r("qm", False, subject="math", grade=5),
            _r("qv", False, subject="vietnamese", grade=5),
        ])
        later = datetime.now(VN) + timedelta(days=2)
        due_math = get_due_reviews(self.db, subject="math", grade=5, now=later)
        self.assertEqual([d["question_id"] for d in due_math], ["qm"])
        due_all = get_due_reviews(self.db, now=later)
        self.assertEqual(len(due_all), 2)

    def test_stats_counts_due_and_tracked(self):
        record_review_results(self.db, [_r("q1", False), _r("q2", True)])
        stats = get_review_stats(self.db, now=datetime.now(VN) + timedelta(days=2))
        self.assertEqual(stats["total_tracked"], 2)
        self.assertEqual(stats["due_count"], 2)
        stats_now = get_review_stats(self.db, now=datetime.now(VN))
        self.assertEqual(stats_now["due_count"], 0)


if __name__ == "__main__":
    unittest.main()
