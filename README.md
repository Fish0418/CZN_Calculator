# CZN Calculator

A web-based calculator for managing character and partner progression in the game, helping you track required materials for leveling, ascension, and potential upgrades.

## Features

- **Character & Partner Management**: Add characters and partners to your building queue
- **Material Calculation**: Automatically calculates required materials for upgrades
- **Inventory Tracking**: Keep track of your available materials
- **Smart Conversion**: Automatically converts between different material tiers
- **Potential System**: Set target levels for all 9 potential nodes (with defaults: 10,7,7,3,3,1,1,1,1)

## Prerequisites

- Python 3.x
- Flask 3.0.0

## Installation

1. **Clone or download this repository** to your local machine

2. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Setup

### Initialize the Databases

The calculator uses two SQLite databases that need to be created before first use:

1. **Create the building database** (`building.db`):
   ```bash
   python init_db.py
   ```
   This creates the database for tracking characters/partners you're building and their potential levels.

2. **Create the items database** (`items.db`):
   ```bash
   python init_items_db.py
   ```
   This creates the database for tracking your inventory from the `items.csv` file.

You should see confirmation messages:
```
Database initialized successfully!
Items database initialized successfully!
```

**Note**: The databases are automatically created when you first run `app.py`, but you can create them manually using the commands above if needed.

## Running the Application

1. **Start the Flask application**:
   ```bash
   python app.py
   ```

2. **Access the web interface**:
   - Open your web browser and navigate to: **http://127.0.0.1:5001**
   - The application runs on **localhost** (127.0.0.1) on **port 5001**

3. **Stop the application**:
   - Press `Ctrl+C` in the terminal where the app is running

## Usage Guide

### Adding Characters/Partners

1. Click the **"Add Character/Partner"** button
2. Select either **Combatants** (characters) or **Partners**
3. Search for and select the unit you want to add
4. Set the current and goal levels:
   - **Level**: 1-60
   - **Ascension**: 0-5
   - **Potentials** (Characters only): Set current and target levels for all 9 nodes
     - Default targets: 10,7,7,3,3,1,1,1,1
5. Click **Save** to add the unit to your building queue

### Managing Inventory

1. Click the **"Edit Inventory"** button
2. Update the amounts for your available materials
3. Click **Save** to update your inventory
4. Materials are grouped by type for easy editing

### Viewing Required Materials

- The **Required Materials** section shows all materials needed for your building queue
- Materials are displayed with current available vs. required amounts
- Completed materials show a checkmark (✓)
- Click on any material to edit its inventory amount
- The calculator automatically:
  - Converts between material tiers (_1, _2, _3)
  - Uses universal materials when specific ones are short
  - Shows XP materials in convenient units (k for thousands)

### Material Conversion Ratios

- **Regular Materials**: 3:1 ratio (3× tier N = 1× tier N+1)
- **EXP Materials**: 
  - 1× `Char_Level_1` / `Part_Level_1` = 100 XP
  - 1× `Char_Level_2` / `Part_Level_2` = 500 XP (5× tier 1)
  - 1× `Char_Level_3` / `Part_Level_3` = 2,000 XP (20× tier 1)

### Upgrading Units

1. Click on a unit card to view details
2. Click the **Upgrade** button to:
   - Check if you have enough materials
   - Consume the required materials from your inventory
   - Complete the upgrade

### Editing/Removing Units

1. Click on a unit card to view details
2. Use **Edit** to modify current/goal stats
3. Use **Remove** to delete the unit from your queue

## File Structure

```
CZN_Calculator/
├── app.py                  # Main Flask application
├── init_db.py              # Database initialization for building queue
├── init_items_db.py        # Database initialization for inventory
├── requirements.txt        # Python dependencies
├── building.db            # Building queue database (created on first run)
├── items.db               # Inventory database (created on first run)
├── characters.csv         # Character data
├── partners.csv           # Partner data
├── items.csv              # Items template
├── char_levels.csv        # Character level XP requirements
├── part_levels.csv        # Partner level XP requirements
├── char_ascend.csv        # Character ascension costs
├── part_ascend.csv        # Partner ascension costs
├── potential.csv          # Potential upgrade costs
├── templates/
│   └── index.html         # Main HTML template
└── static/
    ├── styles.css         # Application styles
    ├── script.js          # Frontend JavaScript
    └── images/            # Character and partner images
        ├── characters/
        └── partners/
```

## Troubleshooting

### Port Already in Use
If port 5001 is already in use, edit `app.py` and change the port number:
```python
app.run(host='127.0.0.1', port=5002, debug=True)  # Change to any available port
```

### Missing Images
- Character images should be in `static/images/characters/`
- Partner images should be in `static/images/partners/`
- Image files must match the exact character/partner name (e.g., `Maribell.png`, `Narja.png`)

### Database Errors
If you encounter database errors:
1. Delete `building.db` and `items.db`
2. Run `python init_db.py` and `python init_items_db.py` again
3. Restart the application

### Browser Cache
If changes aren't appearing:
- Hard refresh your browser: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
- Or clear your browser cache

## Tips

- The calculator saves your inventory and building queue in the databases
- Your data persists between sessions
- Use the default potential targets (10,7,7,3,3,1,1,1,1) as a starting point
- Universal materials are automatically used when specific materials are insufficient
- Material requirements update in real-time as you add or modify units

## License

This is a personal calculator tool for game progression tracking.
