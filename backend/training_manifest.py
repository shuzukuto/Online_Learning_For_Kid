from __future__ import annotations
"""
EduQuest Pro — Training Manifest Module
Manages metadata of processed exam images/PDFs to prevent redundant processing,
track file contents via SHA-256 checksums, monitor handwriting occurrences,
and minimize API token consumption and OCR overhead.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_MANIFEST_PATH = os.path.join(PROJECT_ROOT, "data", "processed_manifest.json")
VN_TZ = timezone(timedelta(hours=7))


def calculate_file_hash(filepath: str) -> str:
    """
    Calculates SHA-256 hexadecimal digest for a given file.
    Reads file in 64KB chunks to efficiently handle large images and PDF files.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Tệp không tồn tại để tính mã băm SHA-256: {filepath}")

    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_manifest(manifest_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads manifest metadata from JSON file. Returns a default empty structure
    if file does not exist or contains invalid JSON.
    """
    path = manifest_path or DEFAULT_MANIFEST_PATH
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "files" in data:
                    return data
        except Exception as e:
            print(f"[Manifest] Cảnh báo: Không thể đọc tệp manifest ({e}), khởi tạo cấu trúc mới.")

    return {
        "version": "1.0",
        "description": "EduQuest Pro Training Extraction Manifest & Deduplication Registry",
        "created_at": datetime.now(VN_TZ).isoformat(),
        "updated_at": datetime.now(VN_TZ).isoformat(),
        "total_processed_files": 0,
        "total_extracted_questions": 0,
        "handwriting_files_count": 0,
        "files": {}
    }


def save_manifest(manifest_data: Dict[str, Any], manifest_path: Optional[str] = None) -> bool:
    """
    Atomically saves manifest data to JSON file via a temporary file replacement.
    """
    path = manifest_path or DEFAULT_MANIFEST_PATH
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        temp_path = f"{path}.tmp.{os.getpid()}"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
        return True
    except Exception as e:
        print(f"[Manifest] ❌ Lỗi khi lưu manifest ({path}): {e}")
        return False


def is_file_processed(filepath: str, manifest_path: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Checks if a file has already been processed based on SHA-256 hash.
    Returns:
        (True, record_dict) if already recorded in manifest,
        (False, None) if not processed yet or file content has changed.
    """
    if not os.path.exists(filepath):
        return False, None

    manifest = load_manifest(manifest_path)
    file_hash = calculate_file_hash(filepath)

    if file_hash in manifest.get("files", {}):
        return True, manifest["files"][file_hash]

    return False, None


def record_processed_file(
    filepath: str,
    output_json: str,
    questions: List[Dict[str, Any]],
    has_handwriting: Optional[bool] = None,
    manifest_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Records a successfully extracted file into the manifest registry.
    Automatically detects handwriting presence across questions if not explicitly specified.
    Updates aggregate counters and timestamp.
    """
    manifest = load_manifest(manifest_path)
    file_hash = calculate_file_hash(filepath)
    file_size = os.path.getsize(filepath)

    # Automatically deduce handwriting presence if not provided
    if has_handwriting is None:
        has_handwriting = any(bool(q.get("has_handwriting")) for q in questions)

    record = {
        "source_hash": file_hash,
        "filename": os.path.basename(filepath),
        "filepath": os.path.abspath(filepath),
        "file_size_bytes": file_size,
        "output_json": output_json,
        "question_count": len(questions),
        "has_handwriting": bool(has_handwriting),
        "processed_at": datetime.now(VN_TZ).isoformat(),
        "question_ids": [q.get("id") for q in questions if q.get("id")]
    }

    manifest["files"][file_hash] = record

    # Update summary aggregates
    manifest["total_processed_files"] = len(manifest["files"])
    manifest["total_extracted_questions"] = sum(
        item.get("question_count", 0) for item in manifest["files"].values()
    )
    manifest["handwriting_files_count"] = sum(
        1 for item in manifest["files"].values() if item.get("has_handwriting")
    )
    manifest["updated_at"] = datetime.now(VN_TZ).isoformat()

    save_manifest(manifest, manifest_path)
    return record


def get_manifest_summary(manifest_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns a comprehensive statistical summary of the manifest registry.
    """
    manifest = load_manifest(manifest_path)
    total_files = manifest.get("total_processed_files", len(manifest.get("files", {})))
    total_questions = manifest.get("total_extracted_questions", 0)
    hw_files = manifest.get("handwriting_files_count", 0)

    hw_percentage = round((hw_files / total_files * 100), 2) if total_files > 0 else 0.0

    return {
        "total_processed_files": total_files,
        "total_extracted_questions": total_questions,
        "handwriting_files_count": hw_files,
        "handwriting_percentage": hw_percentage,
        "manifest_path": os.path.abspath(manifest_path or DEFAULT_MANIFEST_PATH),
        "last_updated": manifest.get("updated_at", manifest.get("created_at", "N/A"))
    }


def sync_manifest_from_checkpoint(
    checkpoint_path: str,
    input_dir: str,
    output_json: str,
    manifest_path: Optional[str] = None
) -> int:
    """
    Synchronizes an existing checkpoint into manifest if manifest was initialized later.
    Calculates real SHA-256 hashes for each referenced file found in input_dir.
    """
    if not os.path.exists(checkpoint_path):
        return 0

    with open(checkpoint_path, "r", encoding="utf-8") as f:
        checkpoint_data = json.load(f)

    if not isinstance(checkpoint_data, dict):
        return 0

    synced_count = 0
    for filename, questions in checkpoint_data.items():
        filepath = os.path.join(input_dir, filename)
        if os.path.exists(filepath):
            record_processed_file(
                filepath=filepath,
                output_json=output_json,
                questions=questions,
                manifest_path=manifest_path
            )
            synced_count += 1

    return synced_count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EduQuest Pro Training Manifest Manager")
    parser.add_argument("--summary", action="store_true", help="Display manifest summary statistics")
    parser.add_argument("--check", type=str, help="Check if a specific file has been processed")
    parser.add_argument("--sync", action="store_true", help="Sync existing batch checkpoint into manifest")
    args = parser.parse_args()

    if args.summary:
        summary = get_manifest_summary()
        print("=" * 60)
        print("📋 EDUQUEST PRO - TRAINING MANIFEST SUMMARY")
        print("=" * 60)
        print(f"📁 Tệp manifest: {summary['manifest_path']}")
        print(f"📦 Tổng số tệp đã xử lý: {summary['total_processed_files']}")
        print(f"📝 Tổng số câu hỏi đã bóc tách: {summary['total_extracted_questions']}")
        print(f"✍️ Tệp phát hiện chữ viết tay: {summary['handwriting_files_count']} ({summary['handwriting_percentage']}%)")
        print(f"🕒 Lần cập nhật gần nhất: {summary['last_updated']}")
        print("=" * 60)
    elif args.check:
        processed, record = is_file_processed(args.check)
        if processed:
            print(f"✅ Tệp ĐÃ ĐƯỢC XỬ LÝ: {args.check}")
            print(f"   • Mã băm SHA-256: {record['source_hash']}")
            print(f"   • Số câu hỏi: {record['question_count']}")
            print(f"   • Chữ viết tay: {record['has_handwriting']}")
            print(f"   • Thời điểm xử lý: {record['processed_at']}")
        else:
            print(f"❌ Tệp CHƯA ĐƯỢC XỬ LÝ hoặc đã bị chỉnh sửa nội dung: {args.check}")
    elif args.sync:
        checkpoint_file = os.path.join(PROJECT_ROOT, "data", ".batch_checkpoint.json")
        training_dir = os.path.join(PROJECT_ROOT, "data", "training")
        out_json = os.path.join(PROJECT_ROOT, "data", "extracted_training_questions.json")
        count = sync_manifest_from_checkpoint(checkpoint_file, training_dir, out_json)
        print(f"⚡ Đã đồng bộ {count} tệp từ checkpoint vào manifest!")
    else:
        parser.print_help()
