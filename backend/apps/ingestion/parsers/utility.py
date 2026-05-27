# Utility electricity billing CSV parser
# Reads a billing summary CSV from a utility portal (one row per billing period)
# We chose billing summary over interval data because ESG teams report monthly totals,
# not 15-minute readings. Also, billing CSVs are what the finance team already archives.
#
# Key problem: utility billing periods don't line up with calendar months.
# A bill from Jan 15 to Feb 13 covers parts of two months, so we split it by days.

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import io
import csv
import re
import chardet


# Different utility portals use different column names for the same thing
# We try each alias in order until we find one that's in the file
FIELD_NAMES = {
    'account':    ['Account Number', 'Account', 'Account No', 'AccountNumber'],
    'meter':      ['Meter Number', 'Meter ID', 'MeterID', 'Meter'],
    'facility':   ['Facility', 'Facility Name', 'Site', 'Location', 'Service Address'],
    'start':      ['Bill Start Date', 'Service Start', 'Period Start', 'From Date', 'BillStartDate'],
    'end':        ['Bill End Date', 'Service End', 'Period End', 'To Date', 'BillEndDate'],
    'kwh':        ['kWh Usage', 'Usage kWh', 'kWh', 'Energy kWh', 'Consumption (kWh)', 'Usage'],
    'demand':     ['kW Demand', 'Peak Demand kW', 'Demand', 'kW'],
    'tariff':     ['Rate Schedule', 'Tariff', 'Rate Code', 'Tariff Code', 'Rate'],
    'charge':     ['Total Charge', 'Total Amount', 'Bill Amount', 'Total'],
    'currency':   ['Currency', 'Cur', 'Curr'],
    'register':   ['Register', 'Time-of-Use', 'TOU Period', 'Rate Period'],
    'read_type':  ['Read Type', 'Read', 'Meter Read Type'],
}

DATE_FORMATS = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y']


def find_col(headers, field):
    # Look through the aliases for this field and return the first match we find
    aliases = FIELD_NAMES.get(field, [])
    lower_map = {}
    for h in headers:
        lower_map[h.lower()] = h
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


def parse_num(text):
    # Strip currency symbols (£ $ €) and comma thousand separators
    clean = re.sub(r'[£$€,\s]', '', text.strip())
    return Decimal(clean)


def split_billing_months(kwh, start, end):
    # Split the billing period kWh across the calendar months it covers
    # For example a Jan 15 - Feb 13 bill gets split into Jan portion and Feb portion
    # We use simple day-count proration
    if start > end:
        return []

    total_days = (end - start).days + 1
    if total_days <= 0:
        return []

    result = []
    current = start
    while current <= end:
        # Find the last day of the current month
        if current.month == 12:
            last_of_month = date(current.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_of_month = date(current.year, current.month + 1, 1) - timedelta(days=1)

        seg_end  = min(last_of_month, end)
        seg_days = (seg_end - current).days + 1
        seg_kwh  = kwh * Decimal(seg_days) / Decimal(total_days)

        result.append((current, seg_end, seg_kwh.quantize(Decimal('0.001'))))
        current = seg_end + timedelta(days=1)

    return result


def parse_bill_row(row, col_map, row_num):
    errors  = []
    warnings = []

    def get(field):
        col = col_map.get(field)
        return row.get(col, '').strip() if col else ''

    # Parse billing period dates
    try:
        bill_start = parse_date(get('start'))
    except ValueError as e:
        errors.append(str(e))
        bill_start = None

    try:
        bill_end = parse_date(get('end'))
    except ValueError as e:
        errors.append(str(e))
        bill_end = None

    # Parse kWh usage
    raw_kwh = get('kwh')
    try:
        kwh = parse_num(raw_kwh)
    except (InvalidOperation, ValueError):
        errors.append('Could not read kWh: ' + raw_kwh)
        kwh = None

    # Parse demand - this is optional
    demand_kw = None
    raw_demand = get('demand')
    if raw_demand:
        try:
            demand_kw = parse_num(raw_demand)
        except (InvalidOperation, ValueError):
            warnings.append('Could not read kW demand: ' + raw_demand)

    account   = get('account')
    meter     = get('meter')
    facility  = get('facility')
    tariff    = get('tariff')
    register  = get('register') or 'Total'
    read_type = get('read_type') or 'Actual'
    currency  = get('currency') or 'GBP'

    total_charge = None
    raw_charge = get('charge')
    if raw_charge:
        try:
            total_charge = parse_num(raw_charge)
        except (InvalidOperation, ValueError):
            pass

    if errors:
        return [{'ok': False, 'errors': errors, 'suspicious': False, 'data': None, 'raw_data': row}]

    # Flag estimated reads - the utility may revise them in the next bill
    if 'estimated' in read_type.lower():
        warnings.append('Estimated meter read - utility may revise this in the next bill')

    if kwh is not None and kwh <= 0:
        warnings.append('kWh is zero or negative - may be a credit or adjustment row')

    # Split the billing period across calendar months
    segments = split_billing_months(kwh, bill_start, bill_end)

    records = []
    for seg_start, seg_end, seg_kwh in segments:
        data = {
            'scope': 2,
            'ghg_category': 'Purchased electricity',
            'source_type': 'UTILITY_ELECTRICITY',
            'source_id': account + ':' + meter + ':' + str(bill_start),
            'activity_type': 'electricity_consumption',
            'quantity': str(seg_kwh),
            'unit': 'kWh',
            'quantity_original': str(kwh),
            'unit_original': 'kWh',
            'conversion_factor': '1',
            'period_start': seg_start.isoformat(),
            'period_end':   seg_end.isoformat(),
            'facility_code': meter,
            'facility_name': facility,
            'country_code': '',
            'extra_data': {
                'account_number': account,
                'tariff': tariff,
                'register': register,
                'billing_period_start': bill_start.isoformat(),
                'billing_period_end':   bill_end.isoformat(),
                'total_charge': str(total_charge) if total_charge is not None else None,
                'currency': currency,
                'demand_kw': str(demand_kw) if demand_kw is not None else None,
                'read_type': read_type,
                'prorated_from_billing_period': len(segments) > 1,
            },
        }
        records.append({
            'ok': True,
            'errors': [],
            'suspicious': len(warnings) > 0,
            'warnings': warnings,
            'data': data,
            'raw_data': row,
        })

    if not records:
        return [{'ok': False, 'errors': ['Could not create any records from this row'], 'suspicious': False, 'data': None, 'raw_data': row}]

    return records


def parse_utility_file(file_bytes):
    detected = chardet.detect(file_bytes)
    encoding = detected.get('encoding') or 'utf-8'
    try:
        text = file_bytes.decode(encoding)
    except Exception:
        text = file_bytes.decode('utf-8', errors='replace')

    text = text.lstrip('﻿')  # remove BOM

    reader  = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    # Build a map from our field names to the actual column names in this file
    col_map = {}
    for field in FIELD_NAMES:
        col_map[field] = find_col(headers, field)

    if not col_map.get('kwh'):
        return [], ['Could not find a kWh column in this file - check the format']
    if not col_map.get('start') or not col_map.get('end'):
        return [], ['Could not find billing period start/end columns']

    all_rows = []
    for i, row in enumerate(reader, start=1):
        row_records = parse_bill_row(dict(row), col_map, i)
        all_rows.extend(row_records)

    return all_rows, []
