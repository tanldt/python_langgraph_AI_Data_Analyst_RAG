import csv
import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
rows = [
 ('2026-07','Concert',420,42000), ('2026-07','Sports',260,26000),
 ('2026-08','Concert',500,50000), ('2026-08','Sports',300,30000),
 ('2026-09','Concert',260,26000), ('2026-09','Sports',220,22000),
 ('2026-10','Concert',310,31000), ('2026-10','Sports',250,25000),
]
with sqlite3.connect(DATA / 'sales.db') as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS sales (month TEXT, category TEXT, tickets INTEGER, revenue REAL)')
    conn.execute('DELETE FROM sales')
    conn.executemany('INSERT INTO sales VALUES (?,?,?,?)', rows)
with (DATA / 'sales.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['month','category','tickets','revenue'])
    writer.writerows(rows)
print('Created sample SQLite database and CSV')
