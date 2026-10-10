from __future__ import annotations
"""
Unit Tests for EduQuest Pro Training Manifest & Deduplication System
Using standard library unittest.
"""

import os
import sys
import json
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.training_manifest import (
    calculate_file_hash,
    load_manifest,
    save_manifest,
    is_file_processed,
    record_processed_file,
    get_manifest_summary,
)


class TestTrainingManifest(unittest.TestCase):
    def test_calculate_file_hash(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"Hello EduQuest Pro Training Data")
            temp_path = f.name

        try:
            hash_val = calculate_file_hash(temp_path)
            self.assertIsInstance(hash_val, str)
            self.assertEqual(len(hash_val), 64)

            # Hash must be deterministic
            hash_val_2 = calculate_file_hash(temp_path)
            self.assertEqual(hash_val, hash_val_2)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_calculate_file_hash_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            calculate_file_hash("non_existent_file_path_12345.xyz")

    def test_manifest_workflow(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_file = os.path.join(tmp_dir, "test_manifest.json")
            sample_img = os.path.join(tmp_dir, "sample_exam.png")
            with open(sample_img, "wb") as f:
                f.write(b"SAMPLE_IMAGE_DATA_12345")

            # Initially, file should not be processed
            processed, record = is_file_processed(sample_img, manifest_path=manifest_file)
            self.assertFalse(processed)
            self.assertIsNone(record)

            # Record file with 2 questions, no handwriting
            mock_questions = [
                {"id": "q1", "content_text": "Câu 1: 1 + 1 = ?", "has_handwriting": False},
                {"id": "q2", "content_text": "Câu 2: 2 + 2 = ?", "has_handwriting": False},
            ]
            out_json = os.path.join(tmp_dir, "out.json")
            rec = record_processed_file(
                filepath=sample_img,
                output_json=out_json,
                questions=mock_questions,
                manifest_path=manifest_file
            )

            self.assertEqual(rec["question_count"], 2)
            self.assertFalse(rec["has_handwriting"])
            self.assertEqual(len(rec["source_hash"]), 64)

            # Now file should be recognized as processed
            is_proc, proc_rec = is_file_processed(sample_img, manifest_path=manifest_file)
            self.assertTrue(is_proc)
            self.assertEqual(proc_rec["question_count"], 2)
            self.assertEqual(proc_rec["filename"], "sample_exam.png")

            # Check summary
            summary = get_manifest_summary(manifest_path=manifest_file)
            self.assertEqual(summary["total_processed_files"], 1)
            self.assertEqual(summary["total_extracted_questions"], 2)
            self.assertEqual(summary["handwriting_files_count"], 0)
            self.assertEqual(summary["handwriting_percentage"], 0.0)

            # Now record another file with handwriting
            sample_img_2 = os.path.join(tmp_dir, "sample_exam_2.png")
            with open(sample_img_2, "wb") as f:
                f.write(b"SAMPLE_IMAGE_WITH_HANDWRITING_98765")

            mock_hw_questions = [
                {"id": "q3", "content_text": "Câu 3", "has_handwriting": True}
            ]
            record_processed_file(
                filepath=sample_img_2,
                output_json=out_json,
                questions=mock_hw_questions,
                manifest_path=manifest_file
            )

            summary_2 = get_manifest_summary(manifest_path=manifest_file)
            self.assertEqual(summary_2["total_processed_files"], 2)
            self.assertEqual(summary_2["total_extracted_questions"], 3)
            self.assertEqual(summary_2["handwriting_files_count"], 1)
            self.assertEqual(summary_2["handwriting_percentage"], 50.0)


if __name__ == "__main__":
    unittest.main()
