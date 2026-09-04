import sqlite3
import os

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'data', 'cmfit.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Double quotes around "order" escape the SQL reserved word
    cursor.execute('ALTER TABLE exercise ADD COLUMN "order" INTEGER DEFAULT 0 NOT NULL;')
    conn.commit()
    print("Successfully added 'order' column to Exercise table.")
except sqlite3.OperationalError as e:
    print("Error:", e)
finally:
    conn.close()