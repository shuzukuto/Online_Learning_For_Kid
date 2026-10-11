"""EduQuest Pro — database package (tach tu backend/database.py, P1.1).
Giu nguyen import cu: backend/database.py la shim re-export tu day."""
from __future__ import annotations

from backend.db.base import (
    VN_TZ,
    DB_PATH,
    _stats_cache,
    STATS_CACHE_TTL,
    invalidate_stats_cache,
    compute_content_hash,
    get_connection,
    resequence_question_numbers,
)

from backend.db.schema import (
    init_db,
)

from backend.db.questions import (
    compute_source_detail,
    row_to_dict,
    get_questions,
    get_question_by_id,
    find_duplicate_question_id,
    insert_or_update_question,
    bulk_insert_questions,
    get_duplicate_questions_summary,
    clean_duplicate_questions,
    auto_generate_exam_questions,
    fetch_diverse_replacement_question,
    delete_question,
    bulk_delete_questions,
    bulk_update_questions_grade,
    get_stats,
    get_stats_count,
    maybe_resequence_deferred,
)

from backend.db.exams import (
    create_exam,
    get_exams,
    get_exam_by_id,
    delete_exam,
)

from backend.db.practice import (
    save_practice_history,
    get_practice_history,
    get_practice_history_by_id,
    _evaluate_badges,
    get_practice_analytics,
)

from backend.db.ocr import (
    _ocr_corrections_cache,
    OCR_CORRECTIONS_TTL,
    invalidate_ocr_corrections_cache,
    record_ocr_learning_diff,
    get_ocr_corrections_map,
    get_ocr_corrections,
    add_manual_ocr_correction,
    delete_ocr_correction,
    clear_all_ocr_corrections,
)

from backend.db.logs_config import (
    log_collector_event,
    get_collector_logs,
    clear_collector_logs,
    get_system_config,
    set_system_config,
)

from backend.db.diagnostics import (
    run_database_diagnostics,
    fix_database_issues,
)

from backend.db.review import (
    get_due_reviews,
    get_review_state,
    get_review_stats,
    record_review_results,
)
