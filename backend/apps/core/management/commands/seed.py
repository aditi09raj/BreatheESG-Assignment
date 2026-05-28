"""
Seed the database with a demo tenant, data sources, and sample emission records.
Run: python manage.py seed
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.timezone import now
from datetime import date
from decimal import Decimal

from apps.core.models import Tenant
from apps.ingestion.models import DataSource, IngestionRun, RawRecord
from apps.review.models import EmissionRecord


SAMPLE_RECORDS = [
    # SAP Scope 1 — fuel consumption
    dict(scope=1, ghg_category='Stationary combustion', source_type='SAP_FUEL',
         source_id='4900012345', activity_type='diesel', quantity=Decimal('500'),
         unit='L', quantity_original=Decimal('500'), unit_original='L', conversion_factor=Decimal('1'),
         period_start=date(2024, 1, 15), period_end=date(2024, 1, 15),
         facility_code='DE01', facility_name='Berlin HQ', country_code='DE',
         extra_data={'material_number': 'DIESEL-ULS-001', 'material_description': 'Diesel B7',
                     'movement_type': '261', 'cost_center': '', 'order': '100001234'},
         review_status='PENDING'),
    dict(scope=1, ghg_category='Stationary combustion', source_type='SAP_FUEL',
         source_id='4900012346', activity_type='petrol', quantity=Decimal('120'),
         unit='L', quantity_original=Decimal('120'), unit_original='L', conversion_factor=Decimal('1'),
         period_start=date(2024, 1, 16), period_end=date(2024, 1, 16),
         facility_code='DE02', facility_name='Munich Plant', country_code='DE',
         extra_data={'material_number': 'BENZIN-95', 'material_description': 'Benzin 95 RON',
                     'movement_type': '201', 'cost_center': 'MAINT-HVAC-02', 'order': ''},
         review_status='PENDING'),
    dict(scope=1, ghg_category='Stationary combustion', source_type='SAP_FUEL',
         source_id='4900012347', activity_type='natural_gas', quantity=Decimal('850'),
         unit='M3', quantity_original=Decimal('850'), unit_original='M3', conversion_factor=Decimal('1'),
         period_start=date(2024, 1, 20), period_end=date(2024, 1, 20),
         facility_code='DE01', facility_name='Berlin HQ', country_code='DE',
         extra_data={'material_number': 'ERDGAS-NG', 'material_description': 'Erdgas Niederdrucknetz',
                     'movement_type': '201', 'cost_center': 'UTILS-DE01', 'order': ''},
         review_status='FLAGGED'),
    dict(scope=1, ghg_category='Stationary combustion', source_type='SAP_FUEL',
         source_id='4900012348', activity_type='heating_oil', quantity=Decimal('2000'),
         unit='L', quantity_original=Decimal('528.344'), unit_original='GAL', conversion_factor=Decimal('3.78541'),
         period_start=date(2024, 2, 5), period_end=date(2024, 2, 5),
         facility_code='UK01', facility_name='London Office', country_code='GB',
         extra_data={'material_number': 'HEIZOL-EL', 'material_description': 'Heating Oil (Extra Light)',
                     'movement_type': '261', 'cost_center': '', 'order': '100001289'},
         review_status='APPROVED'),
    dict(scope=1, ghg_category='Stationary combustion', source_type='SAP_FUEL',
         source_id='4900012349', activity_type='diesel', quantity=Decimal('1250.5'),
         unit='L', quantity_original=Decimal('1250.5'), unit_original='L', conversion_factor=Decimal('1'),
         period_start=date(2024, 2, 28), period_end=date(2024, 2, 28),
         facility_code='DE02', facility_name='Munich Plant', country_code='DE',
         extra_data={'material_number': 'DIESEL-ULS-001', 'material_description': 'Diesel B7',
                     'movement_type': '261', 'cost_center': '', 'order': '100001301'},
         review_status='PENDING'),

    # Utility Scope 2 — electricity
    dict(scope=2, ghg_category='Purchased electricity', source_type='UTILITY_ELECTRICITY',
         source_id='ACC-7413:MTR-0081:2024-01-15', activity_type='electricity_consumption',
         quantity=Decimal('28145.333'), unit='kWh',
         quantity_original=Decimal('48291'), unit_original='kWh', conversion_factor=Decimal('1'),
         period_start=date(2024, 1, 15), period_end=date(2024, 1, 31),
         facility_code='MTR-0081', facility_name='Berlin HQ — Main Feed', country_code='DE',
         extra_data={'account_number': 'ACC-7413', 'tariff': 'BT-H', 'register': 'Total',
                     'billing_period_start': '2024-01-15', 'billing_period_end': '2024-02-13',
                     'total_charge': '4892.40', 'currency': 'EUR', 'demand_kw': '187.4',
                     'read_type': 'Actual', 'prorated_from_billing_period': True},
         review_status='PENDING'),
    dict(scope=2, ghg_category='Purchased electricity', source_type='UTILITY_ELECTRICITY',
         source_id='ACC-7413:MTR-0081:2024-01-15', activity_type='electricity_consumption',
         quantity=Decimal('20145.667'), unit='kWh',
         quantity_original=Decimal('48291'), unit_original='kWh', conversion_factor=Decimal('1'),
         period_start=date(2024, 2, 1), period_end=date(2024, 2, 13),
         facility_code='MTR-0081', facility_name='Berlin HQ — Main Feed', country_code='DE',
         extra_data={'account_number': 'ACC-7413', 'tariff': 'BT-H', 'register': 'Total',
                     'billing_period_start': '2024-01-15', 'billing_period_end': '2024-02-13',
                     'total_charge': '4892.40', 'currency': 'EUR', 'demand_kw': '187.4',
                     'read_type': 'Actual', 'prorated_from_billing_period': True},
         review_status='PENDING'),
    dict(scope=2, ghg_category='Purchased electricity', source_type='UTILITY_ELECTRICITY',
         source_id='ACC-8821:MTR-0142:2024-01-18', activity_type='electricity_consumption',
         quantity=Decimal('61200'), unit='kWh',
         quantity_original=Decimal('61200'), unit_original='kWh', conversion_factor=Decimal('1'),
         period_start=date(2024, 1, 18), period_end=date(2024, 2, 17),
         facility_code='MTR-0142', facility_name='Munich Plant — Industrial Meter', country_code='DE',
         extra_data={'account_number': 'ACC-8821', 'tariff': 'SLP-G', 'register': 'Total',
                     'billing_period_start': '2024-01-18', 'billing_period_end': '2024-02-17',
                     'total_charge': '9180.00', 'currency': 'EUR', 'demand_kw': '411.2',
                     'read_type': 'Estimated', 'prorated_from_billing_period': False},
         review_status='FLAGGED'),
    dict(scope=2, ghg_category='Purchased electricity', source_type='UTILITY_ELECTRICITY',
         source_id='ACC-2290:MTR-0019:2024-01-10', activity_type='electricity_consumption',
         quantity=Decimal('8750'), unit='kWh',
         quantity_original=Decimal('8750'), unit_original='kWh', conversion_factor=Decimal('1'),
         period_start=date(2024, 1, 10), period_end=date(2024, 2, 9),
         facility_code='MTR-0019', facility_name='London Office', country_code='GB',
         extra_data={'account_number': 'ACC-2290', 'tariff': 'E-19', 'register': 'Total',
                     'billing_period_start': '2024-01-10', 'billing_period_end': '2024-02-09',
                     'total_charge': '2187.50', 'currency': 'GBP', 'demand_kw': None,
                     'read_type': 'Actual', 'prorated_from_billing_period': False},
         review_status='APPROVED'),

    # Travel Scope 3 — business travel
    dict(scope=3, ghg_category='Business travel', source_type='TRAVEL',
         source_id='ABC123', activity_type='flight', quantity=Decimal('1'),
         unit='passenger-trip', quantity_original=Decimal('1'), unit_original='passenger-trip', conversion_factor=Decimal('1'),
         period_start=date(2024, 3, 10), period_end=date(2024, 3, 10),
         facility_code='', facility_name='', country_code='',
         extra_data={'vendor': 'United Airlines', 'cost_center': 'CC-SALES-EU',
                     'employee_id': 'EMP-00142', 'employee_name': 'Smith, Jane',
                     'from_city': 'San Francisco', 'to_city': 'New York',
                     'cabin_class': 'economy', 'amount': '847.00', 'currency': 'USD',
                     'business_purpose': 'Client meeting NYC', 'expense_type': 'Airfare'},
         review_status='PENDING'),
    dict(scope=3, ghg_category='Business travel', source_type='TRAVEL',
         source_id='ABC123', activity_type='hotel', quantity=Decimal('2'),
         unit='room-night', quantity_original=Decimal('2'), unit_original='room-night', conversion_factor=Decimal('1'),
         period_start=date(2024, 3, 10), period_end=date(2024, 3, 10),
         facility_code='', facility_name='', country_code='',
         extra_data={'vendor': 'Marriott Times Square', 'cost_center': 'CC-SALES-EU',
                     'employee_id': 'EMP-00142', 'employee_name': 'Smith, Jane',
                     'city': 'New York', 'nights': 2, 'amount': '490.00', 'currency': 'USD',
                     'business_purpose': 'Client meeting NYC', 'expense_type': 'Hotel'},
         review_status='PENDING'),
    dict(scope=3, ghg_category='Business travel', source_type='TRAVEL',
         source_id='DEF456', activity_type='flight', quantity=Decimal('1'),
         unit='passenger-trip', quantity_original=Decimal('1'), unit_original='passenger-trip', conversion_factor=Decimal('1'),
         period_start=date(2024, 3, 14), period_end=date(2024, 3, 14),
         facility_code='', facility_name='', country_code='',
         extra_data={'vendor': 'Lufthansa', 'cost_center': 'CC-ENG-DE',
                     'employee_id': 'EMP-00087', 'employee_name': 'Müller, Klaus',
                     'from_city': 'Munich', 'to_city': 'Singapore',
                     'cabin_class': 'business', 'amount': '3840.00', 'currency': 'EUR',
                     'business_purpose': 'APAC partner summit', 'expense_type': 'Airfare'},
         review_status='FLAGGED'),
    dict(scope=3, ghg_category='Business travel', source_type='TRAVEL',
         source_id='GHI789', activity_type='car_rental', quantity=Decimal('1'),
         unit='trip', quantity_original=Decimal('1'), unit_original='trip', conversion_factor=Decimal('1'),
         period_start=date(2024, 3, 18), period_end=date(2024, 3, 18),
         facility_code='', facility_name='', country_code='',
         extra_data={'vendor': 'Hertz', 'cost_center': 'CC-SALES-EU',
                     'employee_id': 'EMP-00201', 'employee_name': 'Patel, Anita',
                     'amount': '187.50', 'currency': 'USD',
                     'business_purpose': 'Customer site visits', 'expense_type': 'Car Rental'},
         review_status='PENDING'),
    dict(scope=3, ghg_category='Business travel', source_type='TRAVEL',
         source_id='JKL012', activity_type='rail', quantity=Decimal('1'),
         unit='passenger-trip', quantity_original=Decimal('1'), unit_original='passenger-trip', conversion_factor=Decimal('1'),
         period_start=date(2024, 3, 21), period_end=date(2024, 3, 21),
         facility_code='', facility_name='', country_code='',
         extra_data={'vendor': 'Deutsche Bahn', 'cost_center': 'CC-ENG-DE',
                     'employee_id': 'EMP-00102', 'employee_name': 'Schmidt, Anna',
                     'from_city': 'Berlin', 'to_city': 'Hamburg',
                     'amount': '89.00', 'currency': 'EUR',
                     'business_purpose': 'Conference attendance', 'expense_type': 'Train'},
         review_status='APPROVED'),
]


class Command(BaseCommand):
    help = 'Seed demo tenant, users, data sources, and emission records'

    def handle(self, *args, **options):
        # Tenant
        tenant, _ = Tenant.objects.get_or_create(name='Acme Manufacturing GmbH', slug='acme')
        self.stdout.write(f'Tenant: {tenant}')

        # Admin user
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write('Created user: admin / admin123')

        # Analyst user
        if not User.objects.filter(username='analyst').exists():
            u = User.objects.create_user('analyst', 'analyst@example.com', 'analyst123')
            self.stdout.write('Created user: analyst / analyst123')

        # Data sources
        sap_source, _ = DataSource.objects.get_or_create(
            tenant=tenant, source_type='SAP_FUEL',
            defaults={'name': 'SAP MM — Fuel & Procurement (DE/UK Plants)',
                      'description': 'MB51 flat-file export, movement types 201/261'},
        )
        util_source, _ = DataSource.objects.get_or_create(
            tenant=tenant, source_type='UTILITY_ELECTRICITY',
            defaults={'name': 'Utility Billing — DE & UK Meters',
                      'description': 'Portal CSV billing summary from Vattenfall (DE) and British Gas (UK)'},
        )
        travel_source, _ = DataSource.objects.get_or_create(
            tenant=tenant, source_type='TRAVEL',
            defaults={'name': 'Concur Expense Report — Q1 2024',
                      'description': 'Standard Accounting Extract v3 from SAP Concur'},
        )

        sources_by_type = {
            'SAP_FUEL': sap_source,
            'UTILITY_ELECTRICITY': util_source,
            'TRAVEL': travel_source,
        }

        # Create one IngestionRun per source type for the seeded records
        runs = {}
        admin_user = User.objects.get(username='admin')
        for src_type, src_obj in sources_by_type.items():
            run, _ = IngestionRun.objects.get_or_create(
                data_source=src_obj,
                file_name=f'seed_data_{src_type.lower()}.csv',
                defaults={
                    'triggered_by': admin_user,
                    'status': 'COMPLETED',
                    'file_hash': f'seed-{src_type}',
                    'records_total': 0,
                    'records_parsed': 0,
                    'records_failed': 0,
                }
            )
            runs[src_type] = run

        # Seed emission records
        created = 0
        for i, rec in enumerate(SAMPLE_RECORDS, start=1):
            src_type = rec['source_type']
            run = runs[src_type]

            raw, _ = RawRecord.objects.get_or_create(
                ingestion_run=run,
                row_index=i,
                defaults={
                    'raw_data': {'seeded': True, 'source_type': src_type},
                    'parse_status': 'OK',
                    'parse_errors': [],
                }
            )

            if not EmissionRecord.objects.filter(raw_record=raw).exists():
                r = rec.copy()
                review_status = r.pop('review_status')
                er = EmissionRecord.objects.create(
                    tenant=tenant,
                    raw_record=raw,
                    **r,
                    review_status=review_status,
                )
                if review_status == 'APPROVED':
                    er.locked_for_audit = True
                    er.locked_at = now()
                    er.reviewed_by = admin_user
                    er.reviewed_at = now()
                    er.save()
                created += 1

        # Update run record counts
        for src_type, run in runs.items():
            cnt = EmissionRecord.objects.filter(raw_record__ingestion_run=run).count()
            run.records_total = cnt
            run.records_parsed = cnt
            run.save()

        self.stdout.write(self.style.SUCCESS(f'Seeded {created} emission records across 3 sources'))
