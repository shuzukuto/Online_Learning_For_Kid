import sqlite3
import json
import re
import hashlib
from datetime import datetime, timezone, timedelta

VN_TZ = timezone(timedelta(hours=7))

def compute_content_hash(text: str) -> str:
    normalized = (text or "").strip().lower()
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()

def clean_unwanted_dollars(text: str) -> str:
    if not text or '$' not in text:
        return text

    # 1. Protect actual currency notation:
    # A single $ followed by digits, with no matching closing $ (e.g. "$6 on Monday", "$8 on Tuesday", "$28", "$30")
    # If the text has currency keywords (dollar, đô la, đô-la, usd)
    has_currency_context = bool(re.search(r'\b(?:dollar|dollars|đô\s*la|đô-la|usd)\b', text, re.IGNORECASE))
    
    currency_tokens = {}
    if has_currency_context:
        def save_currency(m):
            token = f"__CURRENCY_USD_TOKEN_{len(currency_tokens)}__"
            currency_tokens[token] = m.group(0)
            return token
        # Crucial: digits must NOT be immediately followed by closing $ (which would be $3$ pair)
        text = re.sub(r'(?<!\$)\$(?!\$)\s*\d+(?:\.\d+)?\b(?!\$)', save_currency, text)

    def replace_formula(match):
        full = match.group(0)
        inner = match.group(1)
        trimmed = inner.strip()

        if not trimmed:
            return ""

        # Keep LaTeX backslash formulas (\frac, \text, \sqrt, \times, \dots, etc.)
        if '\\' in trimmed:
            return full

        # Keep math script notation ^ and _ (e.g. 7^{2024}, x_1)
        if '^' in trimmed or '_' in trimmed:
            return full

        # Keep single variable / letters ($x$, $y$, $A$, $B$, etc.)
        if re.match(r'^[a-zA-Z]$', trimmed):
            return full

        # Keep math comparison or equation with variables, e.g. x - 38 = 45 or a > b
        if re.search(r'[a-zA-Z]', trimmed) and re.search(r'[=><+\-*/]', trimmed):
            if not re.search(r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', trimmed):
                return full

        # 1. Bare numbers with optional trailing punctuation: e.g. $2$, $ 28$, $ 32.$, $3.5$, $0,25$
        m_num = re.match(r'^(\d+(?:[.,]\d+)?)\s*([.,;:])?$', trimmed)
        if m_num:
            num_part = m_num.group(1)
            punct_part = m_num.group(2) or ""
            return num_part + punct_part

        # 2. Bare single operators: e.g. $ +$, $ -$, $ =$, $ <$, $ >$
        if trimmed in ('+', '-', '=', '<', '>', '≤', '≥', '±', '×', '÷', ':'):
            return trimmed

        # 3. Number with simple common units or words: e.g. $15l$, $7l$, $3 giờ$, $1 giờ 30 phút$, $5 con$, $10 bông hoa$
        if re.match(r'^\d+.*[a-zA-Zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', trimmed):
            if not re.search(r'[+\-*/=><^_{}\\]', trimmed):
                return trimmed

        # 4. Vietnamese text inside $...$:
        if re.search(r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', trimmed):
            if not re.search(r'[\\^_{}]', trimmed):
                return trimmed

        return full

    text = re.sub(r'\$([^$\n]+)\$', replace_formula, text)

    # Restore currency tokens
    for token, original in currency_tokens.items():
        text = text.replace(token, original)

    return text

def clean_options_json(options_str: str) -> str:
    if not options_str or '$' not in options_str:
        return options_str
    try:
        data = json.loads(options_str)
        if isinstance(data, list):
            changed = False
            for item in data:
                if isinstance(item, dict) and "content" in item:
                    old_c = item["content"]
                    new_c = clean_unwanted_dollars(old_c)
                    if new_c != old_c:
                        item["content"] = new_c
                        changed = True
                elif isinstance(item, str):
                    new_item = clean_unwanted_dollars(item)
                    if new_item != item:
                        changed = True
            if changed:
                return json.dumps(data, ensure_ascii=False)
    except Exception:
        pass
    return options_str

def run_fix():
    conn = sqlite3.connect('data/questions.db')
    c = conn.cursor()

    c.execute("""
        SELECT id, content_text, content_html, options, explanation 
        FROM questions 
        WHERE content_text LIKE '%$%' OR content_html LIKE '%$%' OR options LIKE '%$%' OR explanation LIKE '%$%'
    """)
    rows = c.fetchall()
    total_candidates = len(rows)
    print(f"Total candidate questions with '$': {total_candidates}")

    updated_count = 0
    now_iso = datetime.now(VN_TZ).isoformat()

    updates = []
    for r in rows:
        qid, text, html, opts, expl = r
        new_text = clean_unwanted_dollars(text)
        new_html = clean_unwanted_dollars(html)
        new_opts = clean_options_json(opts)
        new_expl = clean_unwanted_dollars(expl)

        if new_text != text or new_html != html or new_opts != opts or new_expl != expl:
            new_hash = compute_content_hash(new_text)
            updates.append((new_text, new_html, new_opts, new_expl, new_hash, now_iso, qid))
            updated_count += 1

    print(f"Applying updates to {len(updates)} questions...")
    c.executemany("""
        UPDATE questions 
        SET content_text = ?, content_html = ?, options = ?, explanation = ?, content_hash = ?, updated_at = ?
        WHERE id = ?
    """, updates)
    conn.commit()
    conn.close()

    print(f"SUCCESS: Updated {updated_count} questions in data/questions.db.")

if __name__ == "__main__":
    run_fix()
