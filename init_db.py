import sqlite3

def init_database():
    conn = sqlite3.connect('building.db')
    cursor = conn.cursor()
    
    # Create table for characters being built
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS building_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'Character' or 'Partner'
            current_level INTEGER DEFAULT 1,
            current_ascension INTEGER DEFAULT 0,
            goal_level INTEGER DEFAULT 60,
            goal_ascension INTEGER DEFAULT 5,
            display_order INTEGER DEFAULT 0
        )
    ''')
    
    # Create table for character potentials (only for characters, not partners)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS building_potentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            potential_type TEXT NOT NULL, -- e.g., 'Comm_Basic_Level', 'Unique_1', etc.
            current_level INTEGER DEFAULT 0,
            goal_level INTEGER DEFAULT 0,
            FOREIGN KEY (character_id) REFERENCES building_characters(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()
