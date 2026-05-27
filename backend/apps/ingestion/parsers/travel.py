# Concur expense report CSV parser
# Reads the Standard Accounting Extract that finance teams export from SAP Concur
#
# Why CSV and not the Concur Itinerary API?
# - Every company has the expense CSV, not everyone has API access set up
# - ~20-30% of flights are booked outside Concur and only show up in the expense export
# - The CSV covers flights, hotels, car rentals all in one file
#
# Big limitation: Concur expense rows have free-text city names ("New York", "NYC", "New York City")
# not IATA codes. We can't compute distances without geocoding which we haven't built yet.
# The city names are saved in extra_data so a future step can look them up.

from datetime import date
from decimal import Decimal, InvalidOperation
import io
import csv
import re
import chardet


# Concur expense type codes and display names -> our activity category
EXPENSE_MAP = {
    'AIRFR':      'flight',
    'AIRFARE':    'flight',
    'AIR':        'flight',
    'HOTEL':      'hotel',
    'LODNG':      'hotel',
    'LODGING':    'hotel',
    'CARRT':      'car_rental',
    'CAR':        'car_rental',
    'RENTAL CAR': 'car_rental',
    'TAXI':       'taxi',
    'TRAIN':      'rail',
    'RAIL':       'rail',
    'GRND':       'ground',
    'GROUND':     'ground',
}

# How Concur writes cabin class vs what we store
CABIN_MAP = {
    'economy':          'economy',
    'economy class':    'economy',
    'coach':            'economy',
    'premium economy':  'premium_economy',
    'premium':          'premium_economy',
    'business':         'business',
    'business class':   'business',
    'first':            'first',
    'first class':      'first',
}

# Different column names for the same field across Concur configurations
FIELD_NAMES = {
    'report_id':    ['Report ID', 'ReportID', 'Report Key'],
    'employee_id':  ['Employee ID', 'EmployeeID', 'Employee Code'],
    'employee':     ['Employee Name', 'Traveler Name', 'Traveller Name'],
    'type':         ['Expense Type', 'ExpenseType', 'Expense Type Name'],
    'type_code':    ['Expense Type Code', 'Expense Code', 'Type Code'],
    'date':         ['Transaction Date', 'Travel Date', 'Date', 'Expense Date'],
    'vendor':       ['Vendor Name', 'Vendor', 'Airline', 'Hotel Name', 'Car Company'],
    'from_city':    ['From City', 'Origin City', 'Departure City', 'Origin'],
    'to_city':      ['To City', 'Destination City', 'Arrival City', 'Destination'],
    'cabin':        ['Class of Service', 'Cabin Class', 'Travel Class', 'Service Class'],
    'check_in':     ['Check-in Date', 'Check In', 'CheckIn', 'Arrival Date'],
    'check_out':    ['Check-out Date', 'Check Out', 'CheckOut', 'Departure Date'],
    'nights':       ['Number of Nights', 'Nights', 'Duration (Nights)'],
    'amount':       ['Transaction Amount', 'Amount', 'Expense Amount'],
    'currency':     ['Transaction Currency', 'Currency', 'Curr'],
    'cost_center':  ['Cost Center', 'CostCenter', 'Department'],
    'personal':     ['Personal Expense', 'Personal', 'Is Personal'],
    'purpose':      ['Business Purpose', 'Purpose', 'Trip Purpose'],
}

DATE_FORMATS = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y']


def find_col(headers, field):
    # Find the actual column name in the file for a given field
    aliases = FIELD_NAMES.get(field, [])
    lower_map = {}
    for h in headers:
        lower_map[h.lower().strip()] = h
    for alias in aliases:
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def parse_date(text):
    from datetime import datetime
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError('Cannot read date: ' + text)


def get_travel_type(expense_type, expense_code):
    # Check if this expense type is one we care about for travel emissions
    code  = (expense_code or '').upper().strip()
    label = (expense_type or '').upper().strip()
    for key in EXPENSE_MAP:
        if key in code or key in label:
            return EXPENSE_MAP[key]
    return None


def parse_travel_row(row, col_map, row_num):
    errors   = []
    warnings = []

    def get(field):
        col = col_map.get(field)
        return row.get(col, '').strip() if col else ''

    # Skip personal expenses - they are not business travel emissions
    personal = get('personal').upper()
    if personal in ('Y', 'YES', 'TRUE', '1'):
        return {'ok': False, 'errors': ['Personal expense - skipped'], 'suspicious': False, 'data': None}

    expense_type = get('type')
    expense_code = get('type_code')
    travel_type  = get_travel_type(expense_type, expense_code)

    if travel_type is None:
        # Meals, parking, etc. are not Scope 3 business travel emissions
        return {
            'ok': False,
            'errors': ['Expense type ' + expense_type + ' is not a travel emission source - skipped'],
            'suspicious': False,
            'data': None,
        }

    # Parse the transaction date
    raw_date = get('date')
    try:
        txn_date = parse_date(raw_date)
    except ValueError:
        errors.append('Could not read date: ' + raw_date)
        txn_date = None

    # Parse the amount
    raw_amount = get('amount')
    try:
        amount = Decimal(re.sub(r'[^0-9.\-]', '', raw_amount)) if raw_amount else None
    except InvalidOperation:
        amount = None
        warnings.append('Could not read amount: ' + raw_amount)

    currency    = get('currency') or 'USD'
    vendor      = get('vendor')
    cost_center = get('cost_center')
    employee_id = get('employee_id')
    employee    = get('employee')
    purpose     = get('purpose')

    # Start building the extra metadata
    extra = {
        'vendor': vendor,
        'cost_center': cost_center,
        'employee_id': employee_id,
        'employee_name': employee,
        'business_purpose': purpose,
        'amount': str(amount) if amount is not None else None,
        'currency': currency,
        'expense_type': expense_type,
    }

    # Set quantity and unit based on the type of travel
    qty  = Decimal('1')
    unit = 'trip'

    if travel_type == 'flight':
        from_city = get('from_city')
        to_city   = get('to_city')
        cabin_raw = get('cabin').lower()
        cabin     = CABIN_MAP.get(cabin_raw, 'economy')

        if not from_city or not to_city:
            warnings.append('Missing origin or destination city - cannot estimate distance')

        extra.update({'from_city': from_city, 'to_city': to_city, 'cabin_class': cabin})
        unit = 'passenger-trip'

    elif travel_type == 'hotel':
        raw_nights    = get('nights')
        raw_check_in  = get('check_in')
        raw_check_out = get('check_out')

        nights = None
        if raw_nights:
            try:
                nights = int(raw_nights)
            except ValueError:
                pass

        # If we don't have a nights column, try to compute from check-in and check-out dates
        if nights is None and raw_check_in and raw_check_out:
            try:
                check_in  = parse_date(raw_check_in)
                check_out = parse_date(raw_check_out)
                nights = (check_out - check_in).days
            except ValueError:
                pass

        if nights is None:
            warnings.append('Could not figure out number of nights - defaulting to 1')
            nights = 1

        qty  = Decimal(nights)
        unit = 'room-night'
        city = get('from_city') or get('to_city')
        extra.update({'nights': nights, 'city': city})

    elif travel_type == 'rail':
        from_city = get('from_city')
        to_city   = get('to_city')
        extra.update({'from_city': from_city, 'to_city': to_city})
        unit = 'passenger-trip'

    if errors:
        return {'ok': False, 'errors': errors, 'suspicious': False, 'data': None}

    period = txn_date.isoformat() if txn_date else None

    data = {
        'scope': 3,
        'ghg_category': 'Business travel',
        'source_type': 'TRAVEL',
        'source_id': get('report_id'),
        'activity_type': travel_type,
        'quantity': str(qty),
        'unit': unit,
        'quantity_original': str(qty),
        'unit_original': unit,
        'conversion_factor': '1',
        'period_start': period,
        'period_end':   period,
        'facility_code': '',
        'facility_name': '',
        'country_code': '',
        'extra_data': extra,
    }

    return {
        'ok': True,
        'errors': [],
        'suspicious': len(warnings) > 0,
        'warnings': warnings,
        'data': data,
    }


def parse_travel_file(file_bytes):
    detected = chardet.detect(file_bytes)
    encoding = detected.get('encoding') or 'utf-8'
    try:
        text = file_bytes.decode(encoding)
    except Exception:
        text = file_bytes.decode('utf-8', errors='replace')

    text = text.lstrip('﻿')  # remove BOM

    reader  = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    # Map our field names to the actual column names in this file
    col_map = {}
    for field in FIELD_NAMES:
        col_map[field] = find_col(headers, field)

    if not col_map.get('type') and not col_map.get('type_code'):
        return [], ['Could not find an Expense Type column - check the file format']

    all_rows = []
    for i, row in enumerate(reader, start=1):
        result = parse_travel_row(dict(row), col_map, i)
        result['raw_data'] = dict(row)
        all_rows.append(result)

    return all_rows, []
