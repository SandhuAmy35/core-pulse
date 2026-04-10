import sqlite3
import os

# Create the layer1_vault directory next to layer2_neural
os.makedirs("../layer1_vault", exist_ok=True)

# Connect to the SQLite database
conn = sqlite3.connect("../layer1_vault/telemetry_vault.sqlite")

# Create the table
conn.execute("""
    CREATE TABLE IF NOT EXISTS telemetry_vault (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        timestamp TEXT, 
        encrypted_payload BLOB, 
        iv BLOB, 
        entropy_score REAL
    )
""")

# Insert dummy data (using ? placeholders to safely pass Python bytes)
conn.execute("""
    INSERT INTO telemetry_vault (timestamp, encrypted_payload, iv, entropy_score) 
    VALUES (?, ?, ?, ?)
""", ('1712750000', b'dummy', b'dummy', 115.5))

conn.commit()
conn.close()

print("[+] Mock Vault Created successfully in layer1_vault!")