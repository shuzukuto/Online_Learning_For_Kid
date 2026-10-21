import sqlite3

conn = sqlite3.connect('data/questions.db')
c = conn.cursor()

# 1. IDs of garbage records to delete:
junk_ids = [
    # Login pages
    'dom_1791117517252_0',
    'dom_1791117518659_0',
    # Welcome / dashboard
    'dom_1791117524686_0',
    # Challenge banners
    'dom_1791117574945_0',
    'dom_1791117675082_0',
    # Text fragment
    'dom_1792505991143_0',
    # Empty options choice
    'vioedu_dom_1790841971042_0',
    '586ff036-fe3',
    '5bb70942-e78',
    # Mock tests
    'test_ai_agent_q_1791515847',
    'test_mock_123',
]

# Add all 28 web_* chapter titles
c.execute("SELECT id FROM questions WHERE id LIKE 'web_%'")
web_ids = [r[0] for r in c.fetchall()]
junk_ids.extend(web_ids)

print(f"Total junk question records to delete: {len(junk_ids)}")

placeholders = ','.join(['?'] * len(junk_ids))
c.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", junk_ids)
print(f"Deleted {c.rowcount} records from questions table.")

# 2. Fix the 4 questions with prepended game modal text
modal_prefix = "Bạn thật xuất sắc Bạn đã chuẩn bị về đích chưa? "
modal_ids = [
    'dom_1791211626390_0',
    'dom_1791211628577_0',
    'dom_1792337312622_0',
    'dom_1792337314937_0'
]

for mid in modal_ids:
    c.execute("SELECT content_text, content_html FROM questions WHERE id = ?", (mid,))
    row = c.fetchone()
    if row:
        t, h = row
        new_t = t.replace("Bạn thật xuất sắc Bạn đã chuẩn bị về đích chưa?", "").strip()
        new_h = h.replace("Bạn thật xuất sắc Bạn đã chuẩn bị về đích chưa?", "").strip()
        c.execute("UPDATE questions SET content_text = ?, content_html = ? WHERE id = ?", (new_t, new_h, mid))
        print(f"Cleaned modal prefix from {mid}")

conn.commit()
conn.close()
print("Junk cleanup completed successfully.")
