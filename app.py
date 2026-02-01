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

def get_tier_conversion(item_name):
    """Get tier conversion multipliers for an item
    
    Returns: (tier2_multiplier, tier3_multiplier)
    XP materials: 5x, 20x
    Other materials: 3x, 9x
    """
    if item_name.startswith('Char_Level_') or item_name.startswith('Part_Level_'):
        return 5, 20
    else:
        return 3, 9

def check_materials_available(needed_materials, inventory):
    """Check if inventory has enough materials with tier conversion and universal fallback
    
    Args:
        needed_materials: dict of {item_name: amount_needed}
        inventory: dict of {item_name: {type, amount}}
    
    Returns:
        (available, missing_items) where available is bool and missing_items is list of shortages
    """
    missing_items = []
    inventory_copy = {k: v['amount'] for k, v in inventory.items()}
    
    # Define universal material mappings
    def get_universal_items(item_name):
        """Get applicable universal items for a given material"""
        # Universals are stored without tier suffix in items.csv
        # and represent tier-1 equivalents for their category
        if item_name.startswith('Char_Ascend_'):
            return ['Char_Ascend_Universal']
        elif item_name.startswith('Part_Ascend_'):
            return ['Part_Ascend_Universal']
        elif item_name.split('_')[0] in ['Passion', 'Instinct', 'Void', 'Order', 'Justice']:
            return ['Potential_Universal']
        return []
    
    for item, needed in needed_materials.items():
        available = inventory_copy.get(item, 0)
        
        # For tiered items (ending in _1, _2, _3), do conversion
        base_match = item.replace('_1', '').replace('_2', '').replace('_3', '')
        tier_match = item[-2:]  # Get _1, _2, or _3
        
        if tier_match in ['_1', '_2', '_3']:
            current_tier = int(tier_match.replace('_', ''))
            tier2_mult, tier3_mult = get_tier_conversion(item)
            total_available_tier1 = 0
            
            # Convert current item to tier 1 equivalent (even if 0)
            if current_tier == 1:
                total_available_tier1 = available
            elif current_tier == 2:
                total_available_tier1 = available * tier2_mult
            elif current_tier == 3:
                total_available_tier1 = available * tier3_mult
            
            # Add other tiers of same type converted to tier 1 equivalent
            for t in [1, 2, 3]:
                if t != current_tier:
                    other_item = f'{base_match}_{t}'
                    other_amount = inventory_copy.get(other_item, 0)
                    if other_amount > 0:
                        if t == 1:
                            total_available_tier1 += other_amount
                        elif t == 2:
                            total_available_tier1 += other_amount * tier2_mult
                        elif t == 3:
                            total_available_tier1 += other_amount * tier3_mult
            
            # Add universal items if applicable (counted as tier 1)
            for universal in get_universal_items(item):
                universal_amount = inventory_copy.get(universal, 0)
                if universal_amount > 0:
                    # Universal items are calculated as tier 1 of their category
                    total_available_tier1 += universal_amount
            
            # Convert needed to tier 1 equivalent
            if current_tier == 1:
                total_needed_tier1 = needed
            elif current_tier == 2:
                total_needed_tier1 = needed * tier2_mult
            elif current_tier == 3:
                total_needed_tier1 = needed * tier3_mult
            
            if total_available_tier1 < total_needed_tier1:
                missing_items.append(f'{item} (need {needed}, have {available})')
        else:
            # Non-tiered items, just check direct amount
            if available < needed:
                missing_items.append(f'{item} (need {needed}, have {available})')
    
    return len(missing_items) == 0, missing_items

def consume_materials(needed_materials, inventory):
    """Consume materials with tier conversion and universal fallback
    
    Args:
        needed_materials: dict of {item_name: amount_needed}
        inventory: dict of {item_name: {type, amount}}
    
    Returns:
        Updated inventory dict
    """
    def get_universal_items(item_name):
        """Get applicable universal items for a given material"""
        if item_name.startswith('Char_Ascend_'):
            parts = item_name.split('_')
            tier = parts[-1]
            return [f'Char_Ascend_Universal_{tier}']
        elif item_name.startswith('Part_Ascend_'):
            parts = item_name.split('_')
            tier = parts[-1]
            return [f'Part_Ascend_Universal_{tier}']
        elif item_name in ['Passion_1', 'Passion_2', 'Passion_3', 'Instinct_1', 'Instinct_2', 'Instinct_3',
                           'Void_1', 'Void_2', 'Void_3', 'Order_1', 'Order_2', 'Order_3',
                           'Justice_1', 'Justice_2', 'Justice_3']:
            tier = item_name.split('_')[-1]
            return [f'Potential_Universal_{tier}']
        return []
    
    for item, needed in needed_materials.items():
        if item not in inventory:
            continue
        
        available = inventory[item]['amount']
        base_match = item.replace('_1', '').replace('_2', '').replace('_3', '')
        tier_match = item[-2:]
        
        if tier_match in ['_1', '_2', '_3']:
            current_tier = int(tier_match.replace('_', ''))
            tier2_mult, tier3_mult = get_tier_conversion(item)
            
            # Convert needed to tier 1 equivalent
            if current_tier == 1:
                total_needed_tier1 = needed
            elif current_tier == 2:
                total_needed_tier1 = needed * tier2_mult
            elif current_tier == 3:
                total_needed_tier1 = needed * tier3_mult
            
            # First use what we have of the current tier
            if current_tier == 1:
                current_use = min(available, needed)
                inventory[item]['amount'] -= current_use
                total_needed_tier1 -= current_use
            elif current_tier == 2:
                current_use = min(available, needed)
                inventory[item]['amount'] -= current_use
                total_needed_tier1 -= current_use * tier2_mult
            elif current_tier == 3:
                current_use = min(available, needed)
                inventory[item]['amount'] -= current_use
                total_needed_tier1 -= current_use * tier3_mult
            
            # Then use higher tiers if needed
            if total_needed_tier1 > 0 and current_tier < 3:
                for t in range(current_tier + 1, 4):
                    other_item = f'{base_match}_{t}'
                    if other_item in inventory and inventory[other_item]['amount'] > 0:
                        if t == 2:
                            can_use = min(inventory[other_item]['amount'], (total_needed_tier1 + tier2_mult - 1) // tier2_mult)
                            inventory[other_item]['amount'] -= can_use
                            total_needed_tier1 -= can_use * tier2_mult
                        elif t == 3:
                            can_use = min(inventory[other_item]['amount'], (total_needed_tier1 + tier3_mult - 1) // tier3_mult)
                            inventory[other_item]['amount'] -= can_use
                            total_needed_tier1 -= can_use * tier3_mult
            
            # Then use lower tiers if needed
            if total_needed_tier1 > 0 and current_tier > 1:
                for t in range(current_tier - 1, 0, -1):
                    other_item = f'{base_match}_{t}'
                    if other_item in inventory and inventory[other_item]['amount'] > 0:
                        can_use = min(inventory[other_item]['amount'], total_needed_tier1)
                        inventory[other_item]['amount'] -= can_use
                        total_needed_tier1 -= can_use
            
            # Finally use universal items if still needed (universal = tier 1 equivalent)
            if total_needed_tier1 > 0:
                for universal in get_universal_items(item):
                    # Universals are stored without tiers and count as tier-1 equivalents
                    if universal in inventory and inventory[universal]['amount'] > 0 and total_needed_tier1 > 0:
                        can_use = min(inventory[universal]['amount'], total_needed_tier1)
                        inventory[universal]['amount'] -= can_use
                        total_needed_tier1 -= can_use
        else:
            # Non-tiered items
            inventory[item]['amount'] -= needed
    
    return inventory

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
    
    # Check if we have enough materials (with tier conversion)
    available, missing = check_materials_available(materials, items)
    if not available:
        conn.close()
        return jsonify({'status': 'error', 'message': f'Not enough materials: {missing[0]}'}), 400
    
    # Consume materials (with tier conversion)
    items = consume_materials(materials, items)
    save_items(items)
    
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
