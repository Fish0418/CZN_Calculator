from flask import Flask, render_template, request, jsonify
import sqlite3
import csv
import os
import json

app = Flask(__name__)

# Database files
DB_FILE = 'building.db'
ITEMS_DB_FILE = 'items.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_items_db_connection():
    """Get items database connection"""
    conn = sqlite3.connect(ITEMS_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def load_csv_data(filename):
    """Load data from CSV file"""
    data = []
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return data

def load_items():
    """Load items inventory from database"""
    items = {}
    conn = get_items_db_connection()
    rows = conn.execute('SELECT * FROM items').fetchall()
    for row in rows:
        items[row['name']] = {
            'type': row['type'],
            'amount': int(row['amount'])
        }
    conn.close()
    return items

def save_items(items):
    """Save items inventory to database"""
    conn = get_items_db_connection()
    for name, data in items.items():
        conn.execute('''
            UPDATE items SET amount = ? WHERE name = ?
        ''', (data['amount'], name))
    conn.commit()
    conn.close()

def get_character_info(name):
    """Get character class and attribute"""
    characters = load_csv_data('characters.csv')
    for char in characters:
        if char['Name'] == name:
            return char
    return None

def get_partner_info(name):
    """Get partner attribute"""
    partners = load_csv_data('partners.csv')
    for partner in partners:
        if partner['Name'] == name:
            return partner
    return None

def calculate_exp_needed(start_level, end_level, csv_file):
    """Calculate total EXP needed from start_level to end_level"""
    levels_data = load_csv_data(csv_file)
    total_exp = 0
    for level_data in levels_data:
        level = int(level_data['Level'])
        if start_level < level <= end_level:
            total_exp += int(level_data['XP'])
    return total_exp

def calculate_materials_for_unit(unit_id):
    """Calculate materials needed for a specific unit"""
    conn = get_db_connection()
    unit = conn.execute('SELECT * FROM building_characters WHERE id = ?', (unit_id,)).fetchone()
    
    if not unit:
        conn.close()
        return {}
    
    materials = {}
    unit_type = unit['type']
    
    # Calculate EXP materials
    csv_file = 'char_levels.csv' if unit_type == 'Character' else 'part_levels.csv'
    exp_needed = calculate_exp_needed(unit['current_level'], unit['goal_level'], csv_file)
    
    # Convert raw XP to number of _1 items (each _1 item = 100 XP)
    prefix = 'Char_Level' if unit_type == 'Character' else 'Part_Level'
    materials[f'{prefix}_1'] = exp_needed // 100
    
    # Calculate ascension materials
    if unit['goal_ascension'] > unit['current_ascension']:
        ascend_csv = 'char_ascend.csv' if unit_type == 'Character' else 'part_ascend.csv'
        ascend_data = load_csv_data(ascend_csv)
        
        if unit_type == 'Character':
            char_info = get_character_info(unit['name'])
            class_name = char_info['Class'] if char_info else 'Universal'
        else:
            partner_info = get_partner_info(unit['name'])
            # For partners, the CSV column is called "Attribute" but it contains the class
            class_name = partner_info['Attribute'] if partner_info else 'Universal'
        
        for ascend in ascend_data:
            ascend_num = int(ascend['Ascend'])
            if unit['current_ascension'] < ascend_num <= unit['goal_ascension']:
                item_type = ascend['Type']
                cost = int(ascend['Cost'])
                
                prefix = 'Char_Ascend' if unit_type == 'Character' else 'Part_Ascend'
                item_name = f'{prefix}_{class_name}_{item_type}'
                
                materials[item_name] = materials.get(item_name, 0) + cost
                
                credit_key = 'Credit' if unit_type == 'Character' else 'Credits'
                materials['Unit'] = materials.get('Unit', 0) + int(ascend[credit_key])
    
    # Calculate potential materials (only for characters)
    if unit_type == 'Character':
        potentials = conn.execute('SELECT * FROM building_potentials WHERE character_id = ?', (unit_id,)).fetchall()
        char_info = get_character_info(unit['name'])
        attribute = char_info['Attribute'] if char_info else None
        
        potential_data = load_csv_data('potential.csv')
        
        for potential in potentials:
            pot_type = potential['potential_type']
            current = potential['current_level']
            goal = potential['goal_level']
            
            if goal > current:
                for pot_row in potential_data:
                    if pot_row['Node'] == pot_type and int(pot_row['Level']) >= current and int(pot_row['Level']) < goal:
                        item_type = pot_row['Type']
                        cost = int(pot_row['Cost'])
                        credit = int(pot_row['Credit'])
                        
                        # Determine which attribute material to use
                        if attribute:
                            item_name = f'{attribute}_{item_type}'
                            materials[item_name] = materials.get(item_name, 0) + cost
                        
                        materials['Unit'] = materials.get('Unit', 0) + credit
                        
                        # Boss materials
                        if pot_row.get('Boss'):
                            boss_key = pot_row['Boss']
                            if char_info and boss_key in char_info:
                                boss_item = char_info[boss_key]
                                boss_amt = int(pot_row['Boss_Amt'])
                                materials[boss_item] = materials.get(boss_item, 0) + boss_amt
                        
                        # Ego crystals
                        if pot_row.get('Ego_Crystal'):
                            ego_amt = int(pot_row['Ego_Crystal'])
                            materials['Ego_Crystal'] = materials.get('Ego_Crystal', 0) + ego_amt
    
    conn.close()
    return materials

def calculate_all_materials():
    """Calculate total materials needed for all units being built"""
    conn = get_db_connection()
    units = conn.execute('SELECT id FROM building_characters ORDER BY display_order').fetchall()
    conn.close()
    
    total_materials = {}
    unit_materials = []
    
    for unit in units:
        mats = calculate_materials_for_unit(unit['id'])
        unit_materials.append({
            'unit_id': unit['id'],
            'materials': mats
        })
        
        for item, amount in mats.items():
            total_materials[item] = total_materials.get(item, 0) + amount
    
    return total_materials, unit_materials

@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/api/characters')
def get_characters():
    """Get all characters"""
    characters = load_csv_data('characters.csv')
    return jsonify(characters)

@app.route('/api/partners')
def get_partners():
    """Get all partners"""
    partners = load_csv_data('partners.csv')
    return jsonify(partners)

@app.route('/api/items')
def get_items():
    """Get inventory items"""
    items = load_items()
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def update_items():
    """Update inventory items"""
    data = request.json
    items = load_items()
    
    for item_name, amount in data.items():
        if item_name in items:
            items[item_name]['amount'] = int(amount)
    
    save_items(items)
    return jsonify({'status': 'success'})

@app.route('/api/building', methods=['GET'])
def get_building_units():
    """Get all units being built"""
    conn = get_db_connection()
    units = conn.execute('SELECT * FROM building_characters ORDER BY display_order').fetchall()
    
    result = []
    for unit in units:
        unit_dict = dict(unit)
        
        # Get potentials if character
        if unit['type'] == 'Character':
            potentials = conn.execute('SELECT * FROM building_potentials WHERE character_id = ?', (unit['id'],)).fetchall()
            unit_dict['potentials'] = [dict(p) for p in potentials]
        else:
            unit_dict['potentials'] = []
        
        result.append(unit_dict)
    
    conn.close()
    return jsonify(result)

@app.route('/api/building', methods=['POST'])
def add_building_unit():
    """Add a unit to building list"""
    data = request.json
    conn = get_db_connection()
    
    # Get max display order
    max_order = conn.execute('SELECT MAX(display_order) as max_order FROM building_characters').fetchone()
    next_order = (max_order['max_order'] or 0) + 1
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO building_characters 
        (name, type, current_level, current_ascension, goal_level, goal_ascension, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['name'],
        data['type'],
        data.get('current_level', 1),
        data.get('current_ascension', 0),
        data.get('goal_level', 60),
        data.get('goal_ascension', 5),
        next_order
    ))
    
    unit_id = cursor.lastrowid
    
    # Add potentials if character
    if data['type'] == 'Character' and 'potentials' in data:
        for pot_type, levels in data['potentials'].items():
            cursor.execute('''
                INSERT INTO building_potentials (character_id, potential_type, current_level, goal_level)
                VALUES (?, ?, ?, ?)
            ''', (unit_id, pot_type, levels.get('current', 0), levels.get('goal', 0)))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'id': unit_id})

@app.route('/api/building/<int:unit_id>', methods=['PUT'])
def update_building_unit(unit_id):
    """Update a unit's build data"""
    data = request.json
    conn = get_db_connection()
    
    conn.execute('''
        UPDATE building_characters
        SET current_level = ?, current_ascension = ?, goal_level = ?, goal_ascension = ?
        WHERE id = ?
    ''', (
        data.get('current_level', 1),
        data.get('current_ascension', 0),
        data.get('goal_level', 60),
        data.get('goal_ascension', 5),
        unit_id
    ))
    
    # Update potentials if provided
    if 'potentials' in data:
        # Delete existing potentials
        conn.execute('DELETE FROM building_potentials WHERE character_id = ?', (unit_id,))
        
        # Insert new potentials
        for pot_type, levels in data['potentials'].items():
            conn.execute('''
                INSERT INTO building_potentials (character_id, potential_type, current_level, goal_level)
                VALUES (?, ?, ?, ?)
            ''', (unit_id, pot_type, levels.get('current', 0), levels.get('goal', 0)))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/api/building/<int:unit_id>', methods=['DELETE'])
def delete_building_unit(unit_id):
    """Remove a unit from building list"""
    conn = get_db_connection()
    conn.execute('DELETE FROM building_characters WHERE id = ?', (unit_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/api/building/<int:unit_id>/upgrade', methods=['POST'])
def upgrade_unit(unit_id):
    """Upgrade a unit and consume materials"""
    conn = get_db_connection()
    unit = conn.execute('SELECT * FROM building_characters WHERE id = ?', (unit_id,)).fetchone()
    
    if not unit:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Unit not found'}), 404
    
    # Calculate materials needed
    materials = calculate_materials_for_unit(unit_id)
    
    # Load current inventory
    items = load_items()
    
    # Check if we have enough materials
    for item, needed in materials.items():
        if item not in items or items[item]['amount'] < needed:
            conn.close()
            return jsonify({'status': 'error', 'message': f'Not enough {item}'}), 400
    
    # Consume materials
    for item, needed in materials.items():
        items[item]['amount'] -= needed
    
    save_items(items)
    
    # Keep the unit in the list - don't auto-update current to goal
    # Just consume the materials
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/api/materials')
def get_materials():
    """Get calculated materials for all units"""
    total_materials, unit_materials = calculate_all_materials()
    return jsonify({
        'total': total_materials,
        'by_unit': unit_materials
    })

@app.route('/api/potential_types')
def get_potential_types():
    """Get all potential types"""
    potential_types = [
        'Comm_Basic_Level',
        'Comm_Common_Level',
        'Comm_Unique_Level',
        'Crit_Chance_Level',
        'Crit_Dmg_Level',
        'Unique_1',
        'Unique_2',
        'Unique_3',
        'Unique_4'
    ]
    
    # Get max levels for each type
    # The CSV contains upgrade costs FROM level X, so max achievable level is max CSV level + 1
    potential_data = load_csv_data('potential.csv')
    max_levels = {}
    
    for pot_type in potential_types:
        max_level = 0
        for row in potential_data:
            if row['Node'] == pot_type:
                level = int(row['Level'])
                if level > max_level:
                    max_level = level
        # If level 9 is in CSV, you can upgrade from 9->10, so max is 10
        max_levels[pot_type] = max_level + 1 + 1  # +1 for the upgrade TO level, +1 for inclusive range
    
    return jsonify(max_levels)

if __name__ == '__main__':
    # Initialize databases if they don't exist
    if not os.path.exists(DB_FILE):
        from init_db import init_database
        init_database()
    
    if not os.path.exists(ITEMS_DB_FILE):
        from init_items_db import init_items_database
        init_items_database()
    
    app.run(host='127.0.0.1', port=5001, debug=True)
