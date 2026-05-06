import sqlite3

conn = sqlite3.connect('data/elevator.db')
c = conn.cursor()

# Enable foreign keys for this connection
c.execute("PRAGMA foreign_keys=ON")

# Check if foreign keys are enabled
c.execute("PRAGMA foreign_keys")
print("Foreign keys enabled:", c.fetchone())

# Check foreign key constraints
c.execute("PRAGMA foreign_key_list(inference_results)")
print("FK constraints on inference_results:", c.fetchall())

# Check elevators table schema
c.execute("PRAGMA table_info(elevators)")
print("Elevators schema:", c.fetchall())

# Check if elev-001 exists
c.execute("SELECT id FROM elevators WHERE id='elev-001'")
print("elev-001 exists:", c.fetchone())

# Try manual insert WITH foreign key enforcement
try:
    c.execute("INSERT INTO inference_results (elevator_id, timestamp, model_name, model_version, status, confidence, health_score, features_json, synced) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              ('elev-001', '2026-05-06T10:00:00', 'test', 'v1', 'NORMAL', 0.9, 85.0, '{}', 0))
    conn.commit()
    print("Manual insert with FK enabled: SUCCESS")
    # Clean up
    c.execute("DELETE FROM inference_results WHERE model_name='test'")
    conn.commit()
except Exception as e:
    print("Manual insert with FK enabled FAILED:", e)

conn.close()
