from __future__ import annotations
"""
EduQuest Pro — Batch Training Data Extractor
Extracts questions, ABCD options, correct answers, pedagogical explanations,
grade levels (including Grade 0 for Kindergarten), subjects, and visual diagrams
from exam images in data/training/ using AI Vision.
"""

import os
import sys
import glob
import json
import uuid
import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.ai_vision import extract_questions_with_ai_vision
from backend.database import insert_or_update_question
from backend.training_manifest import (
    is_file_processed,
    record_processed_file,
    get_manifest_summary,
)

VN_TZ = timezone(timedelta(hours=7))
MEDIA_DIR = os.path.join(PROJECT_ROOT, "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(description="EduQuest Pro - Batch Training Data Extractor")
    parser.add_argument("--input", "-i", default=os.path.join(PROJECT_ROOT, "data", "training"),
                        help="Input directory containing question images")
    parser.add_argument("--output", "-o", default=os.path.join(PROJECT_ROOT, "data", "extracted_training_questions.json"),
                        help="Output JSON file path")
    parser.add_argument("--limit", "-l", type=int, default=None,
                        help="Limit number of images to process")
    parser.add_argument("--checkpoint", "-c", default=os.path.join(PROJECT_ROOT, "data", ".batch_checkpoint.json"),
                        help="Checkpoint file to resume interrupted runs")
    parser.add_argument("--manifest", "-m", default=os.path.join(PROJECT_ROOT, "data", "processed_manifest.json"),
                        help="Path to deduplication manifest registry file")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force re-extraction of all files even if already recorded in manifest")
    parser.add_argument("--import-json", type=str, default=None,
                        help="Import an existing extracted JSON file directly into questions.db")
    parser.add_argument("--sample", action="store_true",
                        help="Run only on a 3-image diverse test sample")
    return parser.parse_args()


def load_checkpoint(checkpoint_path: str) -> Dict[str, List[Dict[str, Any]]]:
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[Checkpoint] Không thể đọc checkpoint cũ: {e}")
    return {}


def save_checkpoint(checkpoint_path: str, data: Dict[str, List[Dict[str, Any]]]):
    try:
        temp_path = checkpoint_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, checkpoint_path)
    except Exception as e:
        print(f"[Checkpoint] Không thể ghi checkpoint: {e}")


def import_questions_from_json(json_path: str) -> int:
    """Imports questions from JSON file into SQLite questions.db."""
    if not os.path.exists(json_path):
        print(f"❌ Tệp JSON không tồn tại: {json_path}")
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(questions, list):
        print("❌ Cấu trúc JSON không hợp lệ (phải là danh sách câu hỏi).")
        return 0

    print(f"📦 Đang nạp {len(questions)} câu hỏi vào Cơ sở dữ liệu SQLite...")
    inserted_count = 0
    for q in questions:
        try:
            res_id = insert_or_update_question(q, allow_duplicate=False)
            if res_id:
                inserted_count += 1
        except Exception as e:
            print(f"Lỗi nạp câu hỏi: {e}")

    print(f"✅ Đã nạp thành công {inserted_count}/{len(questions)} câu hỏi vào questions.db!")
    return inserted_count


async def run_batch_extraction(args):
    # If import only
    if args.import_json:
        import_questions_from_json(args.import_json)
        return

    # Find image files
    input_dir = args.input
    pattern = os.path.join(input_dir, "*.*")
    all_files = sorted([f for f in glob.glob(pattern) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    
    if not all_files:
        print(f"❌ Không tìm thấy ảnh nào trong: {input_dir}")
        return

    if args.sample:
        # Pick 3 diverse representative images
        sample_names = ["FB_IMG_1791115073510.jpg", "FB_IMG_1791460321701.jpg", "FB_IMG_1791458610972.jpg"]
        files_to_process = [f for f in all_files if os.path.basename(f) in sample_names]
        if not files_to_process:
            files_to_process = all_files[:3]
    elif args.limit:
        files_to_process = all_files[:args.limit]
    else:
        files_to_process = all_files

    print("=" * 70)
    print(f"🚀 BẮT ĐẦU BÓC TÁCH DỮ LIỆU ĐỀ THI: {len(files_to_process)} ẢNH")
    print(f"📁 Thư mục nguồn: {input_dir}")
    print(f"💾 File đầu ra JSON: {args.output}")
    print(f"📋 File manifest: {args.manifest}")
    print(f"⚡ Chế độ ép xử lý lại (--force): {'BẬT (Ghi đè)' if args.force else 'TẮT (Chống trùng lặp)'}")
    print("=" * 70)

    checkpoint = load_checkpoint(args.checkpoint)
    print(f"📌 Đã tìm thấy {len(checkpoint)} ảnh trong checkpoint.")

    extracted_total: List[Dict[str, Any]] = []
    
    for idx, img_path in enumerate(files_to_process):
        filename = os.path.basename(img_path)
        print(f"\n[{idx + 1}/{len(files_to_process)}] Đang xử lý: {filename}...")

        # 1. Deduplication check via Manifest (SHA-256 hash)
        if not args.force:
            is_processed, manifest_info = is_file_processed(img_path, manifest_path=args.manifest)
            if is_processed and manifest_info:
                cached_items = checkpoint.get(filename, [])
                q_count = manifest_info.get("question_count", len(cached_items))
                sha_prefix = manifest_info.get("source_hash", "")[:12]
                hw_tag = " [✍️ Có chữ viết tay]" if manifest_info.get("has_handwriting") else ""
                print(f"  ⚡ [Manifest Skip] Tệp đã bóc tách thành công trước đó (SHA-256: {sha_prefix}..., {q_count} câu hỏi{hw_tag}). Bỏ qua để tiết kiệm token!")
                if cached_items:
                    extracted_total.extend(cached_items)
                continue

        # 2. Checkpoint fallback check if not in manifest
        if not args.force and filename in checkpoint:
            cached_items = checkpoint[filename]
            print(f"  ⚡ Tái sử dụng kết quả đã bóc tách từ Checkpoint ({len(cached_items)} câu hỏi).")
            # Also record into manifest to keep it up to date
            record_processed_file(
                filepath=img_path,
                output_json=args.output,
                questions=cached_items,
                manifest_path=args.manifest
            )
            extracted_total.extend(cached_items)
            continue

        try:
            with open(img_path, "rb") as f_img:
                img_bytes = f_img.read()

            # Copy image to media dir for reference
            ext = os.path.splitext(filename)[1].lower() or ".jpg"
            media_filename = f"source_{uuid.uuid4().hex[:10]}{ext}"
            saved_media_path = os.path.join(MEDIA_DIR, media_filename)
            with open(saved_media_path, "wb") as f_save:
                f_save.write(img_bytes)
            media_url = f"/media/{media_filename}"

            logs: List[str] = []
            qs, engine_used = await extract_questions_with_ai_vision(
                image_bytes=img_bytes,
                filename=filename,
                media_url=media_url,
                log_collector=logs
            )

            # Assign unified metadata & IDs
            formatted_qs = []
            for q_idx, q in enumerate(qs):
                q_id = f"train_{uuid.uuid4().hex[:10]}"
                q["id"] = q_id
                q["source_file_name"] = filename
                q["source_image_url"] = media_url
                q["created_at"] = datetime.now(VN_TZ).isoformat()
                q["has_handwriting"] = bool(q.get("has_handwriting", False))
                
                # Derive readable exam name from filename or header
                if q.get("grade") == 0 or "mầm non" in q.get("content_text", "").lower() or "mầm non" in q.get("topic", "").lower():
                    q["grade"] = 0
                    q["exam_name"] = "Đề thi thử Vòng loại Mầm non - Thầy Đặng Việt Hùng"
                    q["source_detail"] = "Đề thi thử Mầm non"
                elif "wkc" in q.get("content_text", "").lower() or "timo" in filename.lower() or "level" in q.get("content_text", "").lower():
                    lvl = q.get("grade", 1)
                    q["exam_name"] = f"TIMO Mock Test - Level {lvl}"
                    q["source_detail"] = "Tài liệu TIMO Premium"
                else:
                    g = q.get("grade", 1)
                    q["exam_name"] = f"Đề thi Thầy Đặng Việt Hùng - Khối {g}"
                    q["source_detail"] = "Đề thi thử Toán tư duy"
                    
                formatted_qs.append(q)

            print(f"  ✅ Trích xuất thành công {len(formatted_qs)} câu hỏi (Engine: {engine_used}).")
            for q in formatted_qs:
                diagram_tag = " [Có hình minh họa 🖼️]" if q.get("images") and any("crop_diag" in img for img in q.get("images", [])) else ""
                hw_tag = " [✍️ Viết tay]" if q.get("has_handwriting") else ""
                print(f"     • Câu {q.get('question_number')}: Khối {q.get('grade')} | Đáp án: {q.get('correct_answer')} | {q.get('difficulty')}{diagram_tag}{hw_tag}")

            if formatted_qs:
                checkpoint[filename] = formatted_qs
                save_checkpoint(args.checkpoint, checkpoint)
                record_processed_file(
                    filepath=img_path,
                    output_json=args.output,
                    questions=formatted_qs,
                    manifest_path=args.manifest
                )
                extracted_total.extend(formatted_qs)

            # Small cooldown to respect provider rate limits
            await asyncio.sleep(2.5)

        except Exception as e:
            print(f"  ❌ Lỗi khi xử lý file {filename}: {e}")

    # Write final aggregated JSON
    with open(args.output, "w", encoding="utf-8") as f_out:
        json.dump(extracted_total, f_out, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("🎉 HOÀN THÀNH QUÁ TRÌNH BÓC TÁCH!")
    print(f"📊 Tổng số ảnh xử lý: {len(files_to_process)}")
    print(f"📝 Tổng số câu hỏi bóc tách: {len(extracted_total)}")
    print(f"📁 Tệp kết quả: {args.output}")

    # Summary statistics
    grade_dist = {}
    diff_dist = {}
    diagram_count = 0
    hw_count = 0
    for q in extracted_total:
        g = q.get("grade", "N/A")
        grade_dist[g] = grade_dist.get(g, 0) + 1
        d = q.get("difficulty", "N/A")
        diff_dist[d] = diff_dist.get(d, 0) + 1
        if any("crop_diag" in img for img in q.get("images", [])):
            diagram_count += 1
        if q.get("has_handwriting"):
            hw_count += 1

    print(f"📈 Phân bố Khối lớp: {grade_dist}")
    print(f"🎯 Phân bố Độ khó: {diff_dist}")
    print(f"🖼️ Số câu có hình minh họa được cắt tự động: {diagram_count}")
    print(f"✍️ Số câu phát hiện chữ viết tay: {hw_count}")

    # Manifest statistics report
    manifest_summary = get_manifest_summary(args.manifest)
    print("=" * 70)
    print("📋 BÁO CÁO HỆ THỐNG MANIFEST CHỐNG TRÙNG LẶP:")
    print(f"   • Tổng số tệp quản lý trong manifest: {manifest_summary['total_processed_files']}")
    print(f"   • Tổng số câu hỏi đã bóc tách: {manifest_summary['total_extracted_questions']}")
    print(f"   • Tệp phát hiện chữ viết tay: {manifest_summary['handwriting_files_count']} ({manifest_summary['handwriting_percentage']}%)")
    print(f"   • Đường dẫn manifest: {manifest_summary['manifest_path']}")
    print("=" * 70)
    print("👉 Để nạp trực tiếp vào cơ sở dữ liệu EduQuest Pro, hãy chạy lệnh:")
    print(f"   python -m backend.batch_training_extractor --import-json {args.output}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_batch_extraction(args))
