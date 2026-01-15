// Global state
let characters = [];
let partners = [];
let items = {};
let buildingUnits = [];
let potentialTypes = {};
let currentEditingUnit = null;
let selectedUnitType = 'Character';

// Default target levels for potentials when adding a new character
const DEFAULT_GOAL_POTENTIALS = {
    Comm_Basic_Level: 10,
    Comm_Common_Level: 7,
    Comm_Unique_Level: 7,
    Crit_Chance_Level: 3,
    Crit_Dmg_Level: 3,
    Unique_1: 1,
    Unique_2: 1,
    Unique_3: 1,
    Unique_4: 1
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    setupEventListeners();
    renderMaterials();
    renderBuildingUnits();
});

// Load all data from API
async function loadData() {
    try {
        const [charsRes, partsRes, itemsRes, buildingRes, potTypesRes] = await Promise.all([
            fetch('/api/characters'),
            fetch('/api/partners'),
            fetch('/api/items'),
            fetch('/api/building'),
            fetch('/api/potential_types')
        ]);
        
        characters = await charsRes.json();
        partners = await partsRes.json();
        items = await itemsRes.json();
        buildingUnits = await buildingRes.json();
        potentialTypes = await potTypesRes.json();
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    // Add unit button
    document.getElementById('addUnitBtn').addEventListener('click', openAddUnitModal);
    
    // Edit inventory button
    document.getElementById('editInventoryBtn').addEventListener('click', openEditInventoryModal);
    
    // Materials header toggle
    document.getElementById('materialsHeader').addEventListener('click', toggleMaterials);
    
    // Modal close buttons
    document.querySelectorAll('.close').forEach(btn => {
        btn.addEventListener('click', function() {
            this.closest('.modal').style.display = 'none';
        });
    });
    
    // Click outside modal to close
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            e.target.style.display = 'none';
        }
    });
    
    // Unit type selector
    document.getElementById('selectCharacterType').addEventListener('click', () => {
        selectedUnitType = 'Character';
        document.getElementById('selectCharacterType').classList.add('active');
        document.getElementById('selectPartnerType').classList.remove('active');
        renderUnitList();
    });
    
    document.getElementById('selectPartnerType').addEventListener('click', () => {
        selectedUnitType = 'Partner';
        document.getElementById('selectPartnerType').classList.add('active');
        document.getElementById('selectCharacterType').classList.remove('active');
        renderUnitList();
    });
    
    // Unit search
    document.getElementById('unitSearch').addEventListener('input', renderUnitList);
    
    // Confirm unit button
    document.getElementById('confirmUnitBtn').addEventListener('click', confirmUnit);
    
    // Edit unit button
    document.getElementById('editUnitBtn').addEventListener('click', () => {
        if (currentEditingUnit) {
            document.getElementById('unitDetailsModal').style.display = 'none';
            const unit = buildingUnits.find(u => u.id === currentEditingUnit.id);
            if (unit) openEditUnitModal(unit);
        }
    });
    
    // Remove unit button
    document.getElementById('removeUnitBtn').addEventListener('click', removeUnit);
    
    // Upgrade unit button
    document.getElementById('upgradeUnitBtn').addEventListener('click', upgradeUnit);
    
    // Save inventory button
    document.getElementById('saveInventoryBtn').addEventListener('click', saveInventory);
    
    // Save item group button
    document.getElementById('saveItemGroupBtn').addEventListener('click', saveItemGroup);
}

// Toggle materials dropdown
function toggleMaterials() {
    const content = document.getElementById('materialsContent');
    const icon = document.querySelector('.toggle-icon');
    
    content.classList.toggle('collapsed');
    icon.classList.toggle('collapsed');
}

// Get item color tier
function getItemTier(itemName) {
    if (itemName.endsWith('_3')) return 'tier-3';
    if (itemName.endsWith('_2')) return 'tier-2';
    if (itemName.endsWith('_1')) return 'tier-1';
    if (itemName.includes('Boss') || itemName === 'Ego_Crystal' || 
        itemName === 'Shards_of_Condemnation' || itemName === 'Eye_of_Wailing_Prodigal') return 'boss';
    if (itemName.includes('Universal') || itemName === 'Unit') return 'universal';
    return 'credit';
}

// Get material sort priority (lower = earlier)
function getMaterialSortPriority(itemName) {
    if (itemName === 'Unit') return 1;
    if (itemName.includes('Char_Level')) return 2;
    if (itemName.includes('Part_Level')) return 3;
    if (itemName === 'Shards_of_Condemnation' || itemName === 'Eye_of_Wailing_Prodigal') return 4;
    if (itemName === 'Ego_Crystal') return 5;
    if (itemName.includes('Char_Ascend')) return 6;
    if (itemName.includes('Part_Ascend')) return 7;
    if (itemName.includes('Potential') || ['Void', 'Passion', 'Order', 'Justice', 'Instinct'].some(attr => itemName.startsWith(attr))) return 8;
    return 9;
}

// Convert materials with automatic tier conversion
function convertMaterials(itemName, needed, available) {
    const result = {
        needed: needed,
        available: available,
        fulfilled: false,
        excess: 0
    };
    
    // For items that can be crafted (have _1, _2, _3 tiers)
    const baseName = itemName.replace(/_[123]$/, '');
    const tier = itemName.match(/_([123])$/);
    
    // Check if this is an XP item (has different conversion ratios)
    const isXPItem = itemName.includes('Level_');
    
    if (tier && !isXPItem) {
        // Regular materials use 3:1 conversion
        const currentTier = parseInt(tier[1]);
        let totalAvailable = available;
        
        // Convert higher tiers down
        for (let t = currentTier + 1; t <= 3; t++) {
            const higherItem = `${baseName}_${t}`;
            if (items[higherItem]) {
                totalAvailable += items[higherItem].amount * 3;
            }
        }
        
        // Convert lower tiers up
        for (let t = currentTier - 1; t >= 1; t--) {
            const lowerItem = `${baseName}_${t}`;
            if (items[lowerItem]) {
                totalAvailable += Math.floor(items[lowerItem].amount / 3);
            }
        }
        
        result.available = totalAvailable;
        result.fulfilled = totalAvailable >= needed;
        result.excess = Math.max(0, totalAvailable - needed);
    } else if (tier && isXPItem) {
        // XP items: _1 = 100, _2 = 500 (5x), _3 = 2000 (20x)
        // Convert all to _1 equivalent for comparison
        const currentTier = parseInt(tier[1]);
        let totalAvailable_1 = 0;
        let totalNeeded_1 = 0;
        
        // Convert current tier to _1 equivalent
        if (currentTier === 1) {
            totalAvailable_1 = available;
            totalNeeded_1 = needed;
        } else if (currentTier === 2) {
            totalAvailable_1 = available * 5;
            totalNeeded_1 = needed * 5;
        } else if (currentTier === 3) {
            totalAvailable_1 = available * 20;
            totalNeeded_1 = needed * 20;
        }
        
        // Add available from all tiers converted to _1
        const item_1 = `${baseName}_1`;
        const item_2 = `${baseName}_2`;
        const item_3 = `${baseName}_3`;
        
        if (items[item_1] && currentTier !== 1) totalAvailable_1 += items[item_1].amount;
        if (items[item_2] && currentTier !== 2) totalAvailable_1 += items[item_2].amount * 5;
        if (items[item_3] && currentTier !== 3) totalAvailable_1 += items[item_3].amount * 20;
        
        // Convert back to current tier for display
        if (currentTier === 1) {
            result.available = totalAvailable_1;
        } else if (currentTier === 2) {
            result.available = Math.floor(totalAvailable_1 / 5);
        } else if (currentTier === 3) {
            result.available = Math.floor(totalAvailable_1 / 20);
        }
        
        result.fulfilled = totalAvailable_1 >= totalNeeded_1;
        result.excess = Math.max(0, result.available - needed);
    } else {
        result.fulfilled = available >= needed;
        result.excess = Math.max(0, available - needed);
    }
    
    return result;
}

// Calculate total materials needed
async function calculateTotalMaterials() {
    try {
        const response = await fetch('/api/materials');
        const data = await response.json();
        return data.total;
    } catch (error) {
        console.error('Error calculating materials:', error);
        return {};
    }
}

// Apply universal conversions to materials
function applyUniversalConversions(materialsNeeded, inventory) {
    const result = {};
    
    // Categories for universal items
    const universalMappings = {
        'Potential_Universal': ['Void_1', 'Passion_1', 'Order_1', 'Justice_1', 'Instinct_1'],
        'Char_Ascend_Universal': ['Char_Ascend_Striker_1', 'Char_Ascend_Vanguard_1', 'Char_Ascend_Controller_1', 
                                  'Char_Ascend_Ranger_1', 'Char_Ascend_Hunter_1', 'Char_Ascend_Psionic_1'],
        'Part_Ascend_Universal': ['Part_Ascend_Striker_1', 'Part_Ascend_Vanguard_1', 'Part_Ascend_Controller_1',
                                  'Part_Ascend_Ranger_1', 'Part_Ascend_Hunter_1', 'Part_Ascend_Psionic_1']
    };
    
    // Track how many universals we've used
    const universalsUsed = {};
    Object.keys(universalMappings).forEach(key => universalsUsed[key] = 0);
    
    // Sort materials to process completed ones last
    const sortedMaterials = Object.entries(materialsNeeded).sort((a, b) => {
        const aFulfilled = convertMaterials(a[0], a[1], inventory[a[0]]?.amount || 0).fulfilled;
        const bFulfilled = convertMaterials(b[0], b[1], inventory[b[0]]?.amount || 0).fulfilled;
        if (aFulfilled !== bFulfilled) return aFulfilled ? 1 : -1;
        return 0;
    });
    
    // Apply universal conversions
    for (const [itemName, needed] of sortedMaterials) {
        let converted = convertMaterials(itemName, needed, inventory[itemName]?.amount || 0);
        
        // Check if this item can use universal
        for (const [universalName, targetItems] of Object.entries(universalMappings)) {
            if (targetItems.some(target => itemName.startsWith(target.replace('_1', '')))) {
                // Check if we have universal items and this item is not yet fulfilled
                const universalAvailable = (inventory[universalName]?.amount || 0) - universalsUsed[universalName];
                if (universalAvailable > 0 && !converted.fulfilled) {
                    const shortage = converted.needed - converted.available;
                    const toUse = Math.min(universalAvailable, shortage);
                    universalsUsed[universalName] += toUse;
                    converted.available += toUse;
                    converted.fulfilled = converted.available >= converted.needed;
                }
            }
        }
        
        result[itemName] = converted;
    }
    
    return result;
}

// Render materials grid
async function renderMaterials() {
    const grid = document.getElementById('materialsGrid');
    grid.innerHTML = '';
    
    const totalMaterials = await calculateTotalMaterials();
    const convertedMaterials = applyUniversalConversions(totalMaterials, items);
    
    // Sort materials: by priority, then by completion status (incomplete first), then by name
    const sortedMaterials = Object.entries(totalMaterials).sort((a, b) => {
        const aConverted = convertedMaterials[a[0]];
        const bConverted = convertedMaterials[b[0]];
        
        // Completed items go to bottom
        if (aConverted.fulfilled !== bConverted.fulfilled) {
            return aConverted.fulfilled ? 1 : -1;
        }
        
        // Sort by priority
        const aPriority = getMaterialSortPriority(a[0]);
        const bPriority = getMaterialSortPriority(b[0]);
        if (aPriority !== bPriority) return aPriority - bPriority;
        
        // Then by name
        return a[0].localeCompare(b[0]);
    });
    
    for (const [itemName, needed] of sortedMaterials) {
        const converted = convertedMaterials[itemName];
        
        const itemDiv = document.createElement('div');
        itemDiv.className = 'material-item';
        itemDiv.onclick = () => openItemGroupModal(itemName);
        
        // Format display for exp items
        let displayNeeded = needed;
        let displayAvailable = converted.available;
        
        if (itemName.includes('Level_')) {
            // Convert to _1 equivalent
            const baseName = itemName.replace(/_[123]$/, '');
            let totalNeeded = needed;
            let totalAvailable = converted.available;
            
            if (itemName.endsWith('_2')) {
                totalNeeded *= 5;
                totalAvailable *= 5;
            } else if (itemName.endsWith('_3')) {
                totalNeeded *= 20;
                totalAvailable *= 20;
            }
            
            displayNeeded = totalNeeded >= 1000 ? (totalNeeded / 1000).toFixed(1) + 'k' : totalNeeded;
            displayAvailable = totalAvailable >= 1000 ? (totalAvailable / 1000).toFixed(1) + 'k' : totalAvailable;
        }
        
        itemDiv.innerHTML = `
            <img src="/static/images/${itemName}.png" alt="${itemName}" class="material-image" 
                 onerror="this.src='/static/images/placeholder.png'">
            <div class="material-bar ${getItemTier(itemName)}"></div>
            <div class="material-info">
                <div class="material-name">${itemName.replace(/_/g, ' ')}</div>
                <div class="material-amount ${converted.fulfilled ? 'completed' : 'incomplete'}">
                    ${displayAvailable} / ${displayNeeded}
                </div>
            </div>
            ${converted.fulfilled ? '<div class="check-mark">✓</div>' : ''}
        `;
        
        grid.appendChild(itemDiv);
    }
}

// Render building units
function renderBuildingUnits() {
    const grid = document.getElementById('unitsGrid');
    grid.innerHTML = '';
    
    buildingUnits.forEach(unit => {
        const unitDiv = document.createElement('div');
        unitDiv.className = 'unit-card';
        unitDiv.onclick = () => openUnitDetailsModal(unit);
        
        const imageName = unit.name;
        const imagePath = unit.type === 'Character' 
            ? `/static/images/characters/${imageName}.png`
            : `/static/images/partners/${imageName}.png`;
        
        // Calculate materials for this unit
        const materials = calculateUnitMaterials(unit);
        const materialsHTML = Object.entries(materials)
            .slice(0, 6)  // Show first 6 materials
            .map(([itemName, needed]) => {
                const available = items[itemName]?.amount || 0;
                const converted = convertMaterials(itemName, needed, available);
                
                return `
                    <div class="material-item">
                        <img src="/static/images/${itemName}.png" alt="${itemName}" class="material-image"
                             onerror="this.src='/static/images/placeholder.png'">
                        <div class="material-bar ${getItemTier(itemName)}"></div>
                        <div class="material-info">
                            <div class="material-amount ${converted.fulfilled ? 'completed' : 'incomplete'}">
                                ${converted.available}/${needed}
                            </div>
                        </div>
                        ${converted.fulfilled ? '<div class="check-mark">✓</div>' : ''}
                    </div>
                `;
            }).join('');
        
        unitDiv.innerHTML = `
            <img src="${imagePath}" alt="${unit.name}" class="unit-card-image"
                 onerror="this.src='/static/images/placeholder.png'">
            <div class="unit-card-name">${unit.name}</div>
            <div class="unit-card-materials">${materialsHTML}</div>
        `;
        
        grid.appendChild(unitDiv);
    });
}

// Calculate materials for a single unit (client-side approximation)
function calculateUnitMaterials(unit) {
    // This is a simplified version - the server does the accurate calculation
    // For display purposes, we'll fetch from server when needed
    return {};
}

// Open add unit modal
function openAddUnitModal() {
    currentEditingUnit = null;
    selectedUnitType = 'Character';
    document.getElementById('selectCharacterType').classList.add('active');
    document.getElementById('selectPartnerType').classList.remove('active');
    document.getElementById('unitSearch').value = '';
    renderUnitList();
    document.getElementById('addUnitModal').style.display = 'block';
}

// Render unit list in add modal
function renderUnitList() {
    const listDiv = document.getElementById('unitList');
    const searchTerm = document.getElementById('unitSearch').value.toLowerCase();
    
    const units = selectedUnitType === 'Character' ? characters : partners;
    const filtered = units.filter(u => u.Name.toLowerCase().includes(searchTerm));
    
    listDiv.innerHTML = filtered.map(unit => {
        const imagePath = selectedUnitType === 'Character'
            ? `/static/images/characters/${unit.Name}.png`
            : `/static/images/partners/${unit.Name}.png`;
        
        return `
            <div class="unit-list-item" onclick="selectUnit('${unit.Name}')">
                <img src="${imagePath}" alt="${unit.Name}" class="unit-list-image"
                     onerror="this.src='/static/images/placeholder.png'">
                <div class="unit-list-name">${unit.Name}</div>
            </div>
        `;
    }).join('');
}

// Select unit from list
window.selectUnit = function(name) {
    document.getElementById('addUnitModal').style.display = 'none';
    openEditUnitModal({ name, type: selectedUnitType });
};

// Open unit details modal
async function openUnitDetailsModal(unit) {
    currentEditingUnit = unit.id ? unit : null;
    
    const modal = document.getElementById('unitDetailsModal');
    const imagePath = unit.type === 'Character'
        ? `/static/images/characters/${unit.name}.png`
        : `/static/images/partners/${unit.name}.png`;
    
    document.getElementById('detailsTitle').textContent = unit.name;
    document.getElementById('detailsImage').src = imagePath;
    document.getElementById('detailsName').textContent = `Level ${unit.current_level} → ${unit.goal_level} | Ascension ${unit.current_ascension} → ${unit.goal_ascension}`;
    
    // Calculate materials for this unit
    const unitMaterials = currentEditingUnit ? await fetchUnitMaterials(unit.id) : {};
    const convertedMaterials = applyUniversalConversions(unitMaterials, items);
    
    // Render materials needed
    const statsDiv = document.querySelector('.details-stats');
    statsDiv.innerHTML = '<h3>Materials Needed:</h3>';
    
    const materialsGrid = document.createElement('div');
    materialsGrid.className = 'unit-materials-grid';
    materialsGrid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 10px; margin-top: 15px;';
    
    Object.entries(convertedMaterials).forEach(([itemName, converted]) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'material-item';
        itemDiv.style.cursor = 'default';
        
        itemDiv.innerHTML = `
            <img src="/static/images/${itemName}.png" alt="${itemName}" class="material-image"
                 onerror="this.src='/static/images/placeholder.png'">
            <div class="material-bar ${getItemTier(itemName)}"></div>
            <div class="material-info">
                <div class="material-name">${itemName.replace(/_/g, ' ')}</div>
                <div class="material-amount ${converted.fulfilled ? 'completed' : 'incomplete'}">
                    ${converted.available} / ${converted.needed}
                </div>
            </div>
            ${converted.fulfilled ? '<div class="check-mark">✓</div>' : ''}
        `;
        
        materialsGrid.appendChild(itemDiv);
    });
    
    statsDiv.appendChild(materialsGrid);
    
    // Show/hide buttons based on whether editing or creating
    if (currentEditingUnit) {
        document.getElementById('editUnitBtn').style.display = 'inline-block';
        document.getElementById('removeUnitBtn').style.display = 'inline-block';
        document.getElementById('upgradeUnitBtn').style.display = 'inline-block';
        document.getElementById('confirmUnitBtn').style.display = 'none';
    } else {
        document.getElementById('editUnitBtn').style.display = 'none';
        document.getElementById('removeUnitBtn').style.display = 'none';
        document.getElementById('upgradeUnitBtn').style.display = 'none';
        document.getElementById('confirmUnitBtn').style.display = 'inline-block';
        document.getElementById('confirmUnitBtn').textContent = 'Add';
    }
    
    modal.style.display = 'block';
}

// Fetch materials for a specific unit
async function fetchUnitMaterials(unitId) {
    try {
        const response = await fetch('/api/materials');
        const data = await response.json();
        const unitMaterials = data.by_unit.find(u => u.unit_id === unitId);
        return unitMaterials ? unitMaterials.materials : {};
    } catch (error) {
        console.error('Error fetching unit materials:', error);
        return {};
    }
}

// Open edit unit modal
function openEditUnitModal(unit) {
    const isNewUnit = !unit.id;
    currentEditingUnit = isNewUnit ? null : unit;
    
    const modal = document.getElementById('editUnitModal');
    const imagePath = unit.type === 'Character'
        ? `/static/images/characters/${unit.name}.png`
        : `/static/images/partners/${unit.name}.png`;
    
    document.getElementById('editDetailsTitle').textContent = 
        unit.type === 'Character' ? 'Character Details' : 'Partner Details';
    document.getElementById('editDetailsImage').src = imagePath;
    document.getElementById('editDetailsName').textContent = unit.name;
    
    // Set level and ascension values
    document.getElementById('editCurrentLevel').value = unit.current_level || 1;
    document.getElementById('editCurrentAscension').value = unit.current_ascension || 0;
    document.getElementById('editGoalLevel').value = unit.goal_level || 60;
    document.getElementById('editGoalAscension').value = unit.goal_ascension || 5;
    
    // Render potentials if character
    if (unit.type === 'Character') {
        renderEditPotentials(unit);
    } else {
        document.getElementById('editCurrentPotentials').innerHTML = '';
        document.getElementById('editGoalPotentials').innerHTML = '';
    }
    
    modal.style.display = 'block';
}

// Render potential selectors
function renderPotentials(unit) {
    const currentDiv = document.getElementById('currentPotentials');
    const goalDiv = document.getElementById('goalPotentials');
    
    const potentialList = [
        'Comm_Basic_Level',
        'Comm_Common_Level',
        'Comm_Unique_Level',
        'Crit_Chance_Level',
        'Crit_Dmg_Level',
        'Unique_1',
        'Unique_2',
        'Unique_3',
        'Unique_4'
    ];
    
    currentDiv.innerHTML = '<h4>Potentials:</h4>';
    goalDiv.innerHTML = '<h4>Potentials:</h4>';
    
    potentialList.forEach(potType => {
        const maxLevel = potentialTypes[potType] || 10;
        const currentValue = getCurrentPotentialLevel(unit, potType);
        const goalValue = getGoalPotentialLevel(unit, potType);
        
        // Current potential
        const currentGroup = document.createElement('div');
        currentGroup.className = 'potential-group';
        currentGroup.innerHTML = `
            <label>${potType.replace(/_/g, ' ')}:</label>
            <select id="current_${potType}" data-pot-type="${potType}">
                ${Array.from({length: maxLevel}, (_, i) => 
                    `<option value="${i}" ${i === currentValue ? 'selected' : ''}>${i}</option>`
                ).join('')}
            </select>
        `;
        currentDiv.appendChild(currentGroup);
        
        // Goal potential
        const goalGroup = document.createElement('div');
        goalGroup.className = 'potential-group';
        goalGroup.innerHTML = `
            <label>${potType.replace(/_/g, ' ')}:</label>
            <select id="goal_${potType}" data-pot-type="${potType}">
                ${Array.from({length: maxLevel}, (_, i) => 
                    `<option value="${i}" ${i === goalValue ? 'selected' : ''}>${i}</option>`
                ).join('')}
            </select>
        `;
        goalDiv.appendChild(goalGroup);
    });
}

// Get current potential level
function getCurrentPotentialLevel(unit, potType) {
    if (!unit.potentials) return 0;
    const pot = unit.potentials.find(p => p.potential_type === potType);
    return pot ? pot.current_level : 0;
}

// Get goal potential level
function getGoalPotentialLevel(unit, potType) {
    if (!unit.potentials) return DEFAULT_GOAL_POTENTIALS[potType] ?? 0;
    const pot = unit.potentials.find(p => p.potential_type === potType);
    return pot ? pot.goal_level : (DEFAULT_GOAL_POTENTIALS[potType] ?? 0);
}

// Render potential selectors for edit modal
function renderEditPotentials(unit) {
    const currentDiv = document.getElementById('editCurrentPotentials');
    const goalDiv = document.getElementById('editGoalPotentials');
    const isNewUnit = !unit.id && (!unit.potentials || unit.potentials.length === 0);
    
    const potentialList = [
        'Comm_Basic_Level',
        'Comm_Common_Level',
        'Comm_Unique_Level',
        'Crit_Chance_Level',
        'Crit_Dmg_Level',
        'Unique_1',
        'Unique_2',
        'Unique_3',
        'Unique_4'
    ];
    
    currentDiv.innerHTML = '<h4>Potentials:</h4>';
    goalDiv.innerHTML = '<h4>Potentials:</h4>';
    
    potentialList.forEach(potType => {
        const maxLevel = potentialTypes[potType] || 10;
        const currentValue = getCurrentPotentialLevel(unit, potType);
        const goalValue = isNewUnit
            ? (DEFAULT_GOAL_POTENTIALS[potType] ?? 0)
            : getGoalPotentialLevel(unit, potType);
        
        // Current potential
        const currentGroup = document.createElement('div');
        currentGroup.className = 'potential-group';
        currentGroup.innerHTML = `
            <label>${potType.replace(/_/g, ' ')}:</label>
            <select id="edit_current_${potType}" data-pot-type="${potType}">
                ${Array.from({length: maxLevel}, (_, i) => 
                    `<option value="${i}" ${i === currentValue ? 'selected' : ''}>${i}</option>`
                ).join('')}
            </select>
        `;
        currentDiv.appendChild(currentGroup);
        
        // Goal potential
        const goalGroup = document.createElement('div');
        goalGroup.className = 'potential-group';
        goalGroup.innerHTML = `
            <label>${potType.replace(/_/g, ' ')}:</label>
            <select id="edit_goal_${potType}" data-pot-type="${potType}">
                ${Array.from({length: maxLevel}, (_, i) => 
                    `<option value="${i}" ${i === goalValue ? 'selected' : ''}>${i}</option>`
                ).join('')}
            </select>
        `;
        goalDiv.appendChild(goalGroup);
    });
}

// Confirm unit (add or update)
async function confirmUnit() {
    const unitData = {
        name: document.getElementById('editDetailsName').textContent,
        type: document.getElementById('editDetailsTitle').textContent.includes('Character') ? 'Character' : 'Partner',
        current_level: parseInt(document.getElementById('editCurrentLevel').value),
        current_ascension: parseInt(document.getElementById('editCurrentAscension').value),
        goal_level: parseInt(document.getElementById('editGoalLevel').value),
        goal_ascension: parseInt(document.getElementById('editGoalAscension').value)
    };
    
    // Collect potentials if character
    if (unitData.type === 'Character') {
        unitData.potentials = {};
        document.querySelectorAll('#editCurrentPotentials select').forEach(select => {
            const potType = select.dataset.potType;
            const currentLevel = parseInt(select.value);
            const goalLevel = parseInt(document.getElementById(`edit_goal_${potType}`).value);
            unitData.potentials[potType] = { current: currentLevel, goal: goalLevel };
        });
    }
    
    try {
        let response;
        if (currentEditingUnit) {
            response = await fetch(`/api/building/${currentEditingUnit.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(unitData)
            });
        } else {
            response = await fetch('/api/building', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(unitData)
            });
        }
        
        if (response.ok) {
            document.getElementById('editUnitModal').style.display = 'none';
            await loadData();
            renderMaterials();
            renderBuildingUnits();
        }
    } catch (error) {
        console.error('Error saving unit:', error);
    }
}

// Remove unit
async function removeUnit() {
    if (!currentEditingUnit) return;
    
    if (!confirm('Are you sure you want to remove this unit?')) return;
    
    try {
        const response = await fetch(`/api/building/${currentEditingUnit.id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            document.getElementById('unitDetailsModal').style.display = 'none';
            await loadData();
            renderMaterials();
            renderBuildingUnits();
        }
    } catch (error) {
        console.error('Error removing unit:', error);
    }
}

// Upgrade unit
async function upgradeUnit() {
    if (!currentEditingUnit) return;
    
    if (!confirm('This will consume materials and upgrade the unit to goal stats. Continue?')) return;
    
    try {
        const response = await fetch(`/api/building/${currentEditingUnit.id}/upgrade`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert('Unit upgraded successfully!');
            document.getElementById('unitDetailsModal').style.display = 'none';
            await loadData();
            renderMaterials();
            renderBuildingUnits();
        } else {
            alert('Error: ' + result.message);
        }
    } catch (error) {
        console.error('Error upgrading unit:', error);
        alert('Error upgrading unit');
    }
}

// Open edit inventory modal
function openEditInventoryModal() {
    const grid = document.getElementById('inventoryGrid');
    grid.innerHTML = '';
    
    // Sort items by type and name
    const sortedItems = Object.entries(items).sort((a, b) => {
        if (a[1].type !== b[1].type) return a[1].type.localeCompare(b[1].type);
        return a[0].localeCompare(b[0]);
    });
    
    sortedItems.forEach(([itemName, itemData]) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'inventory-item';
        itemDiv.innerHTML = `
            <img src="/static/images/${itemName}.png" alt="${itemName}"
                 onerror="this.src='/static/images/placeholder.png'">
            <div class="inventory-item-name">${itemName.replace(/_/g, ' ')}</div>
            <input type="number" id="inv_${itemName}" value="${itemData.amount}" min="0">
        `;
        grid.appendChild(itemDiv);
    });
    
    document.getElementById('editInventoryModal').style.display = 'block';
}

// Save inventory
async function saveInventory() {
    const updates = {};
    
    Object.keys(items).forEach(itemName => {
        const input = document.getElementById(`inv_${itemName}`);
        if (input) {
            updates[itemName] = parseInt(input.value) || 0;
        }
    });
    
    try {
        const response = await fetch('/api/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        
        if (response.ok) {
            document.getElementById('editInventoryModal').style.display = 'none';
            await loadData();
            renderMaterials();
            renderBuildingUnits();
        }
    } catch (error) {
        console.error('Error saving inventory:', error);
    }
}

// Open item group modal (for editing related items like Void_1, Void_2, Void_3)
function openItemGroupModal(itemName) {
    const baseName = itemName.replace(/_[123]$/, '');
    const relatedItems = Object.keys(items).filter(name => {
        const base = name.replace(/_[123]$/, '');
        return base === baseName;
    }).sort();
    
    if (relatedItems.length === 0) {
        relatedItems.push(itemName);
    }
    
    document.getElementById('itemGroupTitle').textContent = `Edit ${baseName.replace(/_/g, ' ')}`;
    
    const content = document.getElementById('itemGroupContent');
    content.innerHTML = relatedItems.map(name => `
        <div class="item-group-item">
            <img src="/static/images/${name}.png" alt="${name}"
                 onerror="this.src='/static/images/placeholder.png'">
            <div class="item-group-info">
                <div class="item-group-name">${name.replace(/_/g, ' ')}</div>
                <input type="number" id="group_${name}" value="${items[name]?.amount || 0}" min="0">
            </div>
        </div>
    `).join('');
    
    document.getElementById('editItemGroupModal').style.display = 'block';
}

// Save item group
async function saveItemGroup() {
    const updates = {};
    
    document.querySelectorAll('#itemGroupContent input').forEach(input => {
        const itemName = input.id.replace('group_', '');
        updates[itemName] = parseInt(input.value) || 0;
    });
    
    try {
        const response = await fetch('/api/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        
        if (response.ok) {
            document.getElementById('editItemGroupModal').style.display = 'none';
            await loadData();
            renderMaterials();
            renderBuildingUnits();
        }
    } catch (error) {
        console.error('Error saving item group:', error);
    }
}
