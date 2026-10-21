import shutil
import os
import datetime

src = 'data/questions.db'
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
dst = f'data/backup/questions_{timestamp}_pre_dollar_fix.db'
os.makedirs('data/backup', exist_ok=True)
shutil.copy2(src, dst)
print(f"Backup created: {dst} | Size: {os.path.getsize(dst)} bytes")
