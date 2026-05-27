# Decision Log

Every ambiguity I resolved, what I chose, why, and what I'd ask the PM.

---

## SAP: which export format?

**Ambiguity:** SAP exposes data via IDocs, flat files, OData services, BAPIs, and custom ABAP reports. Each is a different interface with different complexity.

**Decision:** Flat file (tab-delimited) export from transaction MB51.

**Why:**
- MB51 is the standard report for material document listings — every SAP MM user knows it
- The flat file export (ALV grid → Local File) requires no custom development, no API credentials, no RFC connections
- It's what a sustainability team would realistically ask a client's SAP admin to produce
- IDocs are batch-transfer format between SAP systems; OData requires SAP Gateway configuration the client likely hasn't set up; BAPIs require ABAP development
- The realistic friction point isn't parsing difficulty — it's getting the client to export at all

**What subset I handle:**
- Movement types 201 (GI for cost center) and 261 (GI for production/maintenance order)
- These are the two movement types used for fuel withdrawals in almost every enterprise
- I ignore 262 (reversal of 261) and 202 (reversal of 201) — reversals need netting logic
- I ignore transfer postings (311/312), scrapping (551), and goods receipts entirely

**What I ignore:**
- SAP procurement data (purchase orders, invoice-based spend) — would need Scope 3 Category 1 emission factors
- The MAKT table join for material descriptions — the flat file export doesn't always include it, so I read it from the Materialkurztext column when present and fall back to the material number

**What I'd ask the PM:**
- Do any of the client's plants use non-German SAP locale? The parser handles German decimal format (1.250,500) but would need modification for English locale (1,250.500)
- Are there reversals (202/262) we need to net out, or can we assume the export is already net of reversals?
- What plant codes does the client use? They're 4-char alphanumeric and entirely client-defined — I can't map DE01 → "Berlin HQ" without a lookup table from the client

---

## Utility: which data format?

**Ambiguity:** Utility data can come as Green Button interval CSV (15-min readings), billing summary CSV, PDF bills, or API calls to utility portals.

**Decision:** Billing summary CSV portal export.

**Why:**
- ESG Scope 2 reporting uses monthly or annual totals, not 15-minute interval data
- Billing summary is what the finance team already has for accounts payable — the ESG team doesn't need to request anything new
- PDF parsing would add significant complexity (pdfplumber, layout-sensitive parsing) for no accuracy gain
- Utility APIs (Green Button Connect) require OAuth registration with each utility — a significant per-utility integration effort
- Green Button interval data would give us more precision but requires aggregation, DST handling, and duplicate-read detection that billing summary avoids entirely

**What I handle:**
- Standard billing summary columns (account, meter, facility, dates, kWh, demand, tariff, read type)
- Multi-register TOU meters (separate On-Peak/Off-Peak rows)
- Billing period pro-ration across calendar months

**What I ignore:**
- Reactive power (kVAR) — not relevant to Scope 2 calculations
- Power factor correction charges — accounting detail, not activity data
- Renewable energy certificates / RECs — relevant for market-based Scope 2 but a separate data source
- Gas and water meters — the assignment asked for electricity

**Billing period design decision:**
I chose to pro-rate by days rather than assign the whole bill to the month containing the midpoint (EnergyCAP's approach). Day-proration is more accurate and produces an audit trail that makes the allocation explicit (`prorated_from_billing_period: true` in extra_data). The downside is it creates two EmissionRecords from one source row. I considered keeping them as one record with a note, but splitting is cleaner — each EmissionRecord maps to exactly one calendar period.

**What I'd ask the PM:**
- Is the client using market-based Scope 2 accounting (RECs/GOs) or location-based? The current model only supports location-based
- Do they have sub-meters for specific production lines, or just facility-level meters?
- What utility provider(s)? EDF, Vattenfall, and British Gas all have slightly different CSV formats

---

## Travel: Concur expense CSV vs. Concur Itinerary API

**Ambiguity:** Concur exposes booking data via the Itinerary API (structured IATA airport codes, cabin class codes) and expense data via the Standard Accounting Extract CSV.

**Decision:** Expense report CSV.

**Why:**
- ESG teams universally have access to the expense extract — it's what finance sends to payroll
- The Itinerary API requires OAuth client credentials the client hasn't provisioned for ESG access
- Critical gap: ~20-30% of corporate flights are booked outside Concur Travel (direct airline websites, travel agents) and only appear in the expense system, never in the Itinerary API. API-only approach would systematically undercount emissions
- The expense CSV covers all three travel modes (air, hotel, car) in one file; the Itinerary API has separate endpoints per segment type

**Known limitation this creates:** City names in the expense CSV are free text ("San Francisco", "SF", "SFO"). I can't reliably compute great-circle distance without geocoding, which is a third-party API dependency I didn't want to introduce. The `extra_data.from_city` and `extra_data.to_city` fields preserve the values; a future emission factor calculation step would geocode them.

Navan (TripActions) exports are similar but include `Estimated CO2 (kg)` natively — if the client uses Navan we'd be able to skip the distance estimation problem entirely. Worth asking.

**Hotel row handling:**
Concur sometimes creates one expense row per night of hotel stay when itemisation is enabled. The parser groups by nights count from either the explicit `Number of Nights` column or by computing `check_out - check_in`. This isn't perfect — if an analyst splits a 3-night stay into two separate expense rows, we'd create two records rather than one. Good enough for a prototype; would need deduplication logic in production.

**What I ignore:**
- Meal expenses (MEALF) — not a Scope 3 Category 6 emission source
- Parking (PARKG) — not material
- Multi-currency exchange rate precision — I store transaction currency and amount in `extra_data` but don't convert to a base currency. The emission factor calculation step should use exchange rates at transaction date, not the posted amount which uses a monthly rate

**What I'd ask the PM:**
- Does the client use Concur or Navan? Important because Navan gives CO₂ estimates directly
- Do they have the Itinerary integration enabled? If so, we could cross-reference to get IATA codes for the flights that do go through Concur Travel
- What's the policy on personal expenses that are accidentally submitted — are they already filtered out before the extract, or do we need to rely on the `Personal Expense = Y` flag?

---

## Ingestion mechanism: file upload vs. API pull vs. scheduled job

**Decision:** File upload by the analyst.

**Why:**
- Most realistic for an enterprise client in the first year of an ESG program
- API pull requires credentials, firewall rules, and scheduled infrastructure — all things an enterprise IT team will take months to provision
- File upload is synchronous (no job queues needed for the prototype), auditable (we have the exact file), and gives the analyst control over when data is ingested
- The SHA-256 duplicate check prevents re-ingestion of the same file

**What this gives up:** Manual analyst time each reporting period. In year 2, you'd want to automate this — S3 trigger on file upload, or a direct API pull from SAP's OData service. But that's an integration project, not a data model question.

---

## Review workflow: approve vs. approve-and-lock

**Decision:** Approval immediately locks the record.

**Why:**
The assignment says records go "to auditors" after analyst sign-off. Once an auditor has seen and signed off on a record, it must be immutable — otherwise the audit is meaningless. Locking on approval is the simplest model that maintains this property.

**What this gives up:** A correction workflow after approval. In practice, errors are sometimes discovered after a record has been approved. The correct handling is a supervisor unlock + re-approval trail, which I didn't build (see TRADEOFFS.md). I flagged this in the UI with a "Locked for audit" badge.

---

## Authentication: JWT vs. session

**Decision:** JWT (djangorestframework-simplejwt).

**Why:**
- The React frontend is a separate origin in development (Vite dev server on :5173, Django on :8000)
- Session cookies require careful SameSite configuration across origins; JWT avoids that complexity
- The token refresh flow is already implemented in the API client
- In production with a reverse proxy serving both from the same domain, sessions would be fine too

---

## Single-tenant in the prototype

**Decision:** The prototype hardcodes the first Tenant in the database rather than deriving it from the authenticated user.

**Why:**
- Implementing the full user-to-tenant resolution, per-tenant data isolation, and tenant creation flow is a significant chunk of work orthogonal to the actual ESG problem
- The data model already has all the foreign keys in place — adding the middleware layer is a one-day addition
- I chose to demonstrate the ESG-specific logic (parsers, normalisation, review workflow) rather than generic SaaS plumbing

**What I'd do in a real deployment:** Add a `UserProfile` model with a `tenant` FK, filter all querysets by `request.user.profile.tenant`, and add a tenant admin interface for onboarding new clients.
