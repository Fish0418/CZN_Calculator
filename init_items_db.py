import sqlite3
import csv
import os

def init_items_database():
    """Initialize items database from items.csv"""
    conn = sqlite3.connect('items.db')
    cursor = conn.cursor()
    
    # Create items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            name TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            amount INTEGER DEFAULT 0
        )
    ''')
    
    # Load data from items.csv
    csv_path = os.path.join(os.path.dirname(__file__), 'items.csv')
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute('''
                    INSERT OR REPLACE INTO items (name, type, amount)
                    VALUES (?, ?, ?)
                ''', (row['Name'], row['Type'], int(row['Amount'])))
    
    conn.commit()
    conn.close()
    print("Items database initialized successfully!")

if __name__ == '__main__':
    init_items_database()
