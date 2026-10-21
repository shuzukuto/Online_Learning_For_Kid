import json
import os
import pytest
from backend.app import app

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "tests", "routes_snapshot.json")

def get_all_routes(app):
    results = []
    for r in app.routes:
        if hasattr(r, "path"):
            results.append((r.path, sorted(list(getattr(r, "methods", [])))))
        elif type(r).__name__ == "_IncludedRouter" and hasattr(r, "original_router"):
            for sub_r in r.original_router.routes:
                if hasattr(sub_r, "path"):
                    results.append((sub_r.path, sorted(list(getattr(sub_r, "methods", [])))))
    return sorted(results)

def test_zero_route_drift():
    assert os.path.exists(SNAPSHOT_PATH), "Missing route snapshot file!"
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        expected = json.load(f)

    actual = get_all_routes(app)

    expected_dict = dict(expected)
    actual_dict = dict(actual)

    missing = {k: expected_dict[k] for k in expected_dict if k not in actual_dict}
    added = {k: actual_dict[k] for k in actual_dict if k not in expected_dict}
    method_mismatches = {
        k: {"expected": expected_dict[k], "actual": actual_dict[k]}
        for k in expected_dict
        if k in actual_dict and expected_dict[k] != actual_dict[k]
    }

    assert not missing, f"Missing routes after router decomposition: {missing}"
    assert not added, f"Unexpected added routes: {added}"
    assert not method_mismatches, f"HTTP method mismatches: {method_mismatches}"
    assert len(actual) == len(expected), f"Total route count changed: expected {len(expected)}, got {len(actual)}"
