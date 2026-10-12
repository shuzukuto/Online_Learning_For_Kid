"""RED/GREEN: clean_for_docx must render \\frac{a}{b} as a/b, not ab.

Bug su pham (3 ban phan bien AI deu dung): docx_exporter.py:34-36 xoa
'\\frac' + '{}' → '\\frac{1}{2}' bien thanh '12' trong file Word in cho
hoc sinh tieu hoc. TDD: test RED truoc, regex GREEN sau.

Local thieu python-docx (chi co trong container) → stub module docx
trong sys.modules truoc khi import, vi clean_for_docx la ham pure
khong dung Document.
"""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Stub python-docx (nang, chi co trong container) — clean_for_docx pure.
for _mod in ["docx", "docx.shared", "docx.enum", "docx.enum.text",
             "docx.enum.table", "docx.oxml", "docx.oxml.ns"]:
    sys.modules.setdefault(_mod, MagicMock())

from backend.docx_exporter import clean_for_docx


def test_frac_simple_becomes_slash():
    out = clean_for_docx(r"Tính $\frac{1}{2} + \frac{3}{4}$.")
    assert "12" not in out and "34" not in out, f"phan so dinh so: {out!r}"
    assert "1/2" in out and "3/4" in out, f"thieu dang a/b: {out!r}"


def test_frac_expression_numerator_denominator():
    out = clean_for_docx(r"$M=\frac{a+b}{c}$")
    assert "a+b/c" in out, f"sai dang bieu thuc: {out!r}"


def test_frac_with_sqrt_kept_readable():
    out = clean_for_docx(r"\(\frac{3}{4} + \sqrt{16}\)")
    assert "3/4" in out, f"mat phan so: {out!r}"
    assert "√" in out, f"mat can bac hai: {out!r}"
