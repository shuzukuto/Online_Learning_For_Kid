import sqlite3
import re

conn = sqlite3.connect('data/questions.db')
c = conn.cursor()

# Check for bare numbers in $
c.execute("SELECT id, content_text FROM questions WHERE content_text LIKE '%$%'")
rows = c.fetchall()

bare_pattern = re.compile(r'\$\s*(\d+(?:[.,]\d+)?\s*\.?)\s*\$')
bare_remaining = []
for qid, text in rows:
    m = bare_pattern.findall(text)
    if m:
        bare_remaining.append((qid, text[:120], m))

print(f"Total questions still having '$': {len(rows)}")
print(f"Bare number $...$ remaining: {len(bare_remaining)}")
if bare_remaining:
    for s in bare_remaining[:5]:
        print("Remaining bare:", s)

# Check our user example
c.execute("SELECT id, content_text FROM questions WHERE id = 'dom_1790645330762_0'")
print("\nCheck dom_1790645330762_0:")
print(c.fetchone())

# Check VioEdu examples
c.execute("SELECT id, content_text FROM questions WHERE id IN ('vioedu_5db701f4eaa3f7faff3cfdc3', 'vioedu_5e5516b72dfc852f77f0918d', 'vioedu_5db701f4eaa3f7faff3cfeed')")
print("\nCheck VioEdu examples:")
for r in c.fetchall():
    print(r[0], ':', r[1])

# Check real currency (USD) question
c.execute("SELECT id, content_text FROM questions WHERE id = 'f1d32165-f2d'")
print("\nCheck currency question f1d32165-f2d:")
print(c.fetchone())

# Check real LaTeX formulas
c.execute("SELECT id, content_text FROM questions WHERE id IN ('sample_vioedu_001', 'sample_hkimo_001', 'sample_asmo_001')")
print("\nCheck real LaTeX formulas:")
for r in c.fetchall():
    print(r[0], ':', r[1])
