# SAP MB51 flat file parser
# Reads the tab-delimited export from SAP and pulls out fuel consumption rows
# SAP uses German date format (DD.MM.YYYY) and German decimals (1.250,500 = 1250.5)
# Encoding is usually CP1252 on older systems

import re
from datetime import date
from decimal import Decimal
import chardet


# Maps SAP unit codes to our standard unit + the conversion factor to get there
# Example: GAL is US gallon, we multiply by 3.78541 to get liters
UNIT_MAP = {
    'L':   ('L',  Decimal('1')),
    'LTR': ('L',  Decimal('1')),
    'GL':  ('L',  Decimal('3.78541')),   # US gallon to liters
    'GAL': ('L',  Decimal('3.78541')),   # US gallon to liters
    'M3':  ('M3', Decimal('1')),         # gas m3 stays as m3, not the same as 1000 liters
    'KG':  ('KG', Decimal('1')),
    'KGM': ('KG', Decimal('1')),
    'T':   ('KG', Decimal('1000')),      # metric ton to kg
    'TO':  ('KG', Decimal('1000')),
}

# Movement types that mean the plant actually consumed the fuel
# 201 = goods issue for cost center, 261 = goods issue for order
FUEL_MOVE_TYPES = {'201', '261'}

# Keywords in the material name or number that tell us what kind of fuel it is
# Format is: keyword -> (activity_type, scope_number)
FUEL_MAP = {
    'DIESEL':  ('diesel',      1),
    'BENZIN':  ('petrol',      1),
    'PETROL':  ('petrol',      1),
    'ERDGAS':  ('natural_gas', 1),
    'NATGAS':  ('natural_gas', 1),
    'HEIZOL':  ('heating_oil', 1),
    'LPG':     ('lpg',         1),
    'KOHLE':   ('coal',        1),
    'COAL':    ('coal',        1),
}


def parse_german_num(text):
    # German format uses period for thousands and comma for decimal
    # so "1.250,500" means one thousand two hundred fifty point five
    text = text.strip()
    text = text.replace('.', '')   # drop thousand separator
    text = text.replace(',', '.')  # comma becomes decimal point
    return Decimal(text)


def parse_german_date(text):
    # SAP German date format is DD.MM.YYYY
    text = text.strip()
    match = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', text)
    if not match:
        raise ValueError('Cannot read date: ' + text)
    day   = int(match.group(1))
    month = int(match.group(2))
    year  = int(match.group(3))
    return date(year, month, day)


def get_fuel_type(mat_number, mat_name):
    # Search the material number and description for a known fuel keyword
    combined = (mat_number + ' ' + mat_name).upper()
    for keyword in FUEL_MAP:
        if keyword in combined:
            fuel, scope = FUEL_MAP[keyword]
            return fuel, scope
    return None, None


def parse_sap_row(row, row_num):
    errors = []
    warnings = []

    # Read the posting date
    raw_date = row.get('Buchdat.') or row.get('Buchungsdatum') or row.get('Pstng Date') or ''
    try:
        posting_date = parse_german_date(raw_date)
    except (ValueError, AttributeError):
        errors.append('Could not read date: ' + str(raw_date))
        posting_date = None

    # Check the movement type - skip anything that is not fuel consumption
    move_type = (row.get('BewArt') or row.get('Bewegungsart') or row.get('Mvt Type') or '').strip()
    if move_type not in FUEL_MOVE_TYPES:
        return {
            'ok': False,
            'errors': ['Movement type ' + move_type + ' is not a fuel consumption type, skipped'],
            'suspicious': False,
            'data': None,
        }

    plant      = (row.get('Werk') or row.get('Plant') or '').strip()
    mat_number = (row.get('Material') or row.get('Materialnummer') or '').strip().lstrip('0') or '(unknown)'
    mat_name   = (row.get('Materialkurztext') or row.get('Mat. Short Text') or '').strip()

    # Read the quantity
    raw_qty = row.get('Menge') or row.get('Quantity') or ''
    try:
        original_qty = parse_german_num(str(raw_qty))
    except Exception:
        errors.append('Could not read quantity: ' + str(raw_qty))
        original_qty = None

    # Convert the unit to our standard
    original_unit = (row.get('ME') or row.get('BUn') or row.get('Basismengeneinheit') or '').strip().upper()
    if original_unit not in UNIT_MAP:
        warnings.append('Unknown unit ' + original_unit + ' - no conversion applied')
        normal_unit = original_unit
        factor = Decimal('1')
        normal_qty = original_qty
    else:
        normal_unit, factor = UNIT_MAP[original_unit]
        normal_qty = original_qty * factor if original_qty is not None else None

    # Identify the fuel type from the material
    fuel_type, scope = get_fuel_type(mat_number, mat_name)
    if fuel_type is None:
        warnings.append('Could not identify fuel type for material ' + mat_number + ' / ' + mat_name)
        fuel_type = 'unknown_fuel'
        scope = 1

    cost_center = (row.get('Kostenstelle') or row.get('Cost Ctr') or '').strip()
    order       = (row.get('Auftrag') or row.get('Order') or '').strip().lstrip('0')

    if errors:
        return {'ok': False, 'errors': errors, 'suspicious': False, 'data': None}

    data = {
        'scope': scope,
        'ghg_category': 'Stationary combustion' if fuel_type != 'unknown_fuel' else 'Unknown',
        'source_type': 'SAP_FUEL',
        'source_id': (row.get('Mat. Doc.') or row.get('Beleg') or '').strip(),
        'activity_type': fuel_type,
        'quantity': str(normal_qty),
        'unit': normal_unit,
        'quantity_original': str(original_qty),
        'unit_original': original_unit,
        'conversion_factor': str(factor),
        'period_start': posting_date.isoformat() if posting_date else None,
        'period_end':   posting_date.isoformat() if posting_date else None,
        'facility_code': plant,
        'facility_name': '',
        'country_code': '',
        'extra_data': {
            'material_number': mat_number,
            'material_description': mat_name,
            'movement_type': move_type,
            'cost_center': cost_center,
            'order': order,
        },
    }

    return {
        'ok': True,
        'errors': [],
        'suspicious': len(warnings) > 0,
        'warnings': warnings,
        'data': data,
    }


def parse_sap_file(file_bytes):
    # Detect the file encoding - older SAP uses CP1252, newer uses UTF-8
    detected = chardet.detect(file_bytes)
    encoding = detected.get('encoding') or 'cp1252'
    try:
        text = file_bytes.decode(encoding)
    except Exception:
        text = file_bytes.decode('cp1252', errors='replace')

    text = text.lstrip('﻿')  # remove BOM if present

    lines = text.splitlines()
    if len(lines) < 2:
        return [], ['File is empty or only has a header row']

    # SAP ALV exports are tab-separated
    header_line = lines[0]
    sep = '\t' if '\t' in header_line else ';'
    col_names = [col.strip() for col in header_line.split(sep)]

    all_rows = []
    for i, line in enumerate(lines[1:], start=1):
        if not line.strip():
            continue
        values = line.split(sep)
        # SAP sometimes drops trailing empty columns so we pad the row
        while len(values) < len(col_names):
            values.append('')
        row = {}
        for j, col in enumerate(col_names):
            row[col] = values[j].strip()
        result = parse_sap_row(row, i)
        result['raw_data'] = row
        all_rows.append(result)

    return all_rows, []
