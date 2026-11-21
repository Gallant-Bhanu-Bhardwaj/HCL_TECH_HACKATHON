"""Builds data/ujjwal.db from schema.sql and a seed file. Deletes the old database first.
    python init_db.py                       # small hand-written seed
    python init_db.py data/seed_full.sql    # P2's generated data
"""
import os
import sqlite3
import sys

from app.db import DB_PATH

seed = sys.argv[1] if len(sys.argv) > 1 else "data/seed_small.sql"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

con = sqlite3.connect(DB_PATH)
con.executescript(open("data/schema.sql").read())
con.executescript(open(seed).read())
con.commit()

for table in ["stations", "trains", "train_stops", "fares", "seats", "settings",
              "passengers", "bookings", "booking_travellers"]:
    print(f"{table:20} {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")
con.close()
print(f"Built {DB_PATH} from {seed}")
