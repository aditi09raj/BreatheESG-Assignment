# Source Research

For each of the three data sources: what real-world format I researched, what I learned, what the sample data looks like and why, and what would break in a real deployment.

---

## 1. SAP Fuel & Procurement — MB51 flat file export

### What I researched

SAP exposes materials management data through multiple interfaces. I researched the standard MB51 material document list transaction and its ALV grid export.

The underlying data lives in two tables:
- **MKPF** (MSEG header): document number, posting date, document date
- **MSEG** (document segment): material, plant, quantity, unit, movement type, cost center, order

A typical enterprise export from the ALV grid produces a tab-delimited text file. The German locale configuration — the default for most European enterprises — produces:
- Dates in `DD.MM.YYYY` format (15.01.2024 not 2024-01-15)
- Decimal numbers with comma separator and period thousands separator (1.250,500 = 1250.5)
- Column headers in German (Buchungsdatum, Werk, Menge, Basismengeneinheit)

Non-Unicode SAP ECC instances encode in CP1252 (Windows-1252). S/4HANA is UTF-8 but may include a BOM.

Movement types relevant to fuel consumption:
- **201**: Goods issue for cost center — direct consumption charge (e.g. HVAC gas, boiler fuel)
- **261**: Goods issue for production/maintenance order — consumption against a planned order (e.g. fleet fuel, generator fuel)
- 262 and 202 are the respective reversals; not handled in this prototype

### Sample data design

`sample_data/sap_fuel_DE_UK_2024Q1.txt`

- 10 rows, Q1 2024
- Three plants: DE01 (Berlin HQ), DE02 (Munich Plant), UK01 (London Office)
- Materials: DIESEL-ULS-001 (diesel), BENZIN-95 (petrol), ERDGAS-NG (natural gas), HEIZOL-EL (heating oil), LPG-TANK (LPG)
- Row 4 (HEIZOL-EL, UK01) uses GAL units to exercise the unit conversion path (US gallon → litres, factor 3.78541)
- Row 7 (LPG-TANK) uses KG units — mass-based, stays in KG because CO₂e factors for LPG are per-kg
- German locale: comma decimal, period thousands, DD.MM.YYYY dates
- Mix of movement types 201 and 261 with appropriate cost center / order field usage

### What would break in a real deployment

1. **Locale mismatch**: If the client's SAP user has an English locale, dates come as MM/DD/YYYY and numbers use period decimal. The parser would produce wrong dates and wrong quantities silently. Mitigation: detect locale from the first numeric value containing a period or comma, or ask the client to confirm their SAP GUI locale before the first export.

2. **Missing material descriptions**: The `Materialkurztext` column only appears in MB51 if the SAP user added it to their personal layout. Without it, material classification falls back to the material number (MATNR), which is an opaque 18-char string. The parser handles this by checking both fields and flagging when neither provides a recognisable fuel keyword.

3. **Encoding issues**: German-locale text files from older SAP ECC systems are CP1252. Umlaut characters in material descriptions (Heizöl, Erdgas) will corrupt to `?` if decoded as UTF-8. The parser uses chardet to detect encoding before decoding.

4. **Plant code resolution**: DE01, DE02, UK01 are fabricated codes. Real clients have codes like `1010`, `GPLT`, or `BER1`. Without a plant code → facility name lookup table from the client, the `facility_name` field will be empty and analysts have to know what the codes mean.

5. **Custom MB51 layouts**: SAP users can save personal ALV grid layouts with reordered or renamed columns. The parser relies on recognising column header names. A client who renamed "Menge" to "Qty" in their personal layout would produce a file the parser can't read.

---

## 2. Utility Electricity — Billing summary CSV

### What I researched

Utility portal CSV exports fall into two categories:
- **Green Button interval data**: 15-minute or hourly AMI meter readings with `TYPE, DATE, START TIME, END TIME, USAGE, UNITS, COST` columns
- **Billing summary**: One row per billing period with account, meter, dates, kWh total, demand, tariff, and charges

I chose billing summary because ESG teams report monthly or annual totals, not granular interval data. The interval format would require aggregation with additional complexity around DST transitions and estimated vs. actual reads.

Key finding on billing periods: utility billing cycles are meter-read cycles, not calendar months. A typical commercial account bills from the 15th of one month to the 14th of the next. Assigning the full bill to a single calendar month introduces systematic error — a "January bill" covering Dec 15 – Jan 14 assigns 17 days of December consumption to January.

The EnergyCAP documentation describes two approaches: assign to the month containing the midpoint (simple), or pro-rate by days (accurate). I chose day-proration.

Green Button standard (US): `kWh` column, `DATE` in YYYY-MM-DD, consistent headers. UK/European utilities (EDF, Vattenfall, British Gas): similar structure but `dd/mm/yyyy` dates and amounts in local currency.

### Sample data design

`sample_data/utility_billing_Q1_2024.csv`

- 8 rows, 4 meters, Q1 2024
- Three facilities: Berlin HQ (2 meters: main feed + HVAC supplementary), Munich Plant (1 large industrial meter), London Office (1 small office meter)
- Billing periods straddle calendar months (e.g. Jan 15 – Feb 13)
- Row 3 (Munich Plant MTR-0142, first bill) is marked `Estimated` to exercise the suspicious-read flag
- Berlin HQ main feed is ~48 MWh/month — realistic for a 10,000m² office building
- Munich Plant is ~60 MWh/month — realistic for a light manufacturing facility
- London Office is ~8-9 MWh/month — realistic for a 2,000m² office
- Tariff codes are real German and UK commercial tariff identifiers (BT-H, SLP-G, E-19)

### What would break in a real deployment

1. **Date format variation**: EDF France uses `dd/mm/yyyy`, PG&E uses `mm/dd/yyyy`, Vattenfall Germany uses `yyyy-mm-dd`. The parser tries multiple formats in order but can misparse `01/02/2024` (is it Feb 1 or Jan 2?). Mitigation: ask the client to confirm which utility portals they use and test with a real export before going live.

2. **Column name variation**: Every utility portal names columns differently. "kWh Usage" vs. "Energy kWh" vs. "Consumption (kWh)". The parser uses an alias table, but there will always be a utility it hasn't seen. Mitigation: expose the column mapping as a configurable DataSource field so analysts can correct mismatches without a code deploy.

3. **Multi-register rows**: The parser handles On-Peak/Off-Peak as separate rows. Some portals produce them in wide format (one row with `On_Peak_kWh` and `Off_Peak_kWh` columns). The wide format is not handled and would sum to zero consumption.

4. **Revised estimates**: When a utility issues an estimated read and revises it in the next bill, there's no automatic correction mechanism. The analyst would need to find the original estimated record, reject it, and then the corrected bill would create a new record. This is a significant manual process at scale.

5. **Smart meter vs. legacy meter**: Billing summary works for both. But legacy meters are read every 1-2 months; a missed read creates a double-length billing period. The parser handles this correctly (pro-rates to each month), but the daily consumption for a double-period will look anomalously smooth. An anomaly flag for periods > 35 days would help.

---

## 3. Corporate Travel — Concur expense report CSV

### What I researched

SAP Concur exposes travel data through two interfaces:
- **Expense SAE (Standard Accounting Extract)**: ~400-column flat file of all submitted expenses, one row per expense line
- **Itinerary API v1**: Structured XML/JSON of booked travel segments with IATA airport codes and RBD cabin class codes

I chose the expense extract because:
- It covers 100% of expenses including externally-booked tickets
- ESG teams have access to it via the finance extract; the Itinerary API requires separate OAuth provisioning
- Navan (TripActions) offers a similar CSV export that additionally includes a pre-computed `Estimated CO2 (kg)` column

Critical gap discovered during research: Concur expense rows for airfare contain free-text city names ("San Francisco", "NYC", "New York City") — not IATA codes. Distances cannot be computed without geocoding. The Itinerary API gives IATA codes (SFO, JFK) but only for trips booked through Concur Travel, not external bookings.

Also discovered: Concur sometimes creates one expense row per night of a hotel stay when itemisation is enabled (for per-diem compliance). The parser handles this by reading the `Number of Nights` column or computing from check-in/check-out dates.

Cabin class in the expense CSV is human-readable ("Economy", "Business Class") rather than IATA RBD codes (Y, J, F). For DEFRA emission factor lookups, these map to Economy, Business, Premium Economy, First. Mapping is included in `travel.py:CABIN_CLASS_MAP`.

### Sample data design

`sample_data/travel_concur_Q1_2024.csv`

- 17 rows, 6 employees, Q1 2024
- Mix of expense types: Airfare (7 rows), Hotel (6 rows), Car Rental (1 row), Train (1 row), Taxi (1 row), Meal (1 row)
- The Meal row (MEALF) is deliberately included to test the parser's skip logic — meals are not Scope 3 Cat 6
- Business class long-haul (Müller, Munich→Singapore) alongside economy short-haul to test cabin class variation
- Multi-currency: USD, EUR, GBP, SGD, JPY — mirrors real corporate travel where employees submit in transaction currency
- The UK→Chicago flight (Patel) has From City = "London" and To City = "Chicago" — free text, no IATA codes, exercises the missing-distance warning
- The Munich→Singapore flight uses business class at €3,840 — realistic business class long-haul pricing
- The Frankfurt→Warsaw flight via Ryanair at €89 is included as a realistic low-cost carrier booking to contrast with the long-haul business travel
- The Nakamura Tokyo trip uses JPY for the hotel (realistic — hotel was booked locally)

### What would break in a real deployment

1. **No distances, no CO₂e**: Concur expense CSV has free-text city names, not IATA codes. Without geocoding or a city-pair lookup table, we cannot compute flight distances or CO₂e. This is the single biggest limitation of the expense-CSV approach. Mitigation paths: (a) enrich with the Itinerary API for the ~70-80% of flights booked through Concur Travel; (b) use a geocoding API to normalise city names to coordinates; (c) switch to Navan which provides CO₂ estimates natively.

2. **Hotel grouping failures**: If an analyst submits a 3-night stay as three separate 1-night expense rows (common when Concur itemisation is enabled), the parser creates three separate records rather than one 3-night stay. All three have the same vendor and city; deduplication would need to group by employee + vendor + check-in date, which we don't do.

3. **Personal expense flag reliability**: We skip rows where `Personal Expense = Y`. But if an employee submits a personal expense without flagging it (common), we'd count it as business travel. This isn't a data model problem — it's a policy problem. The `extra_data.personal_expense` flag is preserved so an analyst can catch misclassified rows during review.

4. **Report-level vs. entry-level fields**: Concur's SAE has ~400 columns, many of which are report-level fields repeated on every row. Our column alias table covers the subset we care about. A client using custom expense fields (common in large enterprises) would have additional columns with non-standard names that we'd silently ignore.

5. **Currency conversion**: The prototype stores transaction amounts in original currency. For Scope 3 spending-based metrics, you need a consistent currency. Using the `Posted Amount` (which Concur converts using a monthly rate) is inaccurate; using spot rates at transaction date is correct but requires an FX data source.
