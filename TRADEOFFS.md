# Tradeoffs — Three things I deliberately did not build

## 1. Emissions calculation (tCO₂e)

The app normalises activity data (500 litres of diesel, 48,291 kWh of electricity) but does not compute the resulting CO₂e figures.

**What this means:** An analyst reviewing the data sees quantities and units, not carbon numbers.

**Why I didn't build it:**

Emission factor selection is a compliance decision, not an engineering one. The same litre of diesel has a different CO₂e factor under DEFRA 2023 vs. EPA 2023 vs. IPCC AR6. The geographic grid emission factor for electricity changes every year and varies by country, region, and accounting method (location-based vs. market-based). Using the wrong factor produces a wrong number that will survive audit.

Building emissions calculation correctly requires:
- A versioned emission factor database (DEFRA, EPA, IEA, ecoinvent)
- A decision on which methodology applies per scope (location-based vs. market-based Scope 2)
- A mapping from activity types to emission factor categories
- Uncertainty ranges and data quality scores

That's a substantial research project that belongs in a separate product decision conversation, not a 4-day prototype. What I built instead is the correct foundation: clean, normalised activity data with preserved units and full lineage. Plugging in emission factors is additive.

**What this enables downstream:** Once factors are agreed, the `EmissionRecord.quantity` × `EmissionFactor.co2e_per_unit` calculation is a single database query. No structural changes needed.

---

## 2. Supervisor unlock / post-approval correction workflow

Once a record is approved and locked, it cannot be edited. There is no way to unlock it.

**What this means:** If an error is discovered after approval (e.g. a unit conversion was wrong, or the wrong billing period was assigned), there is no in-app path to fix it.

**Why I didn't build it:**

Post-approval corrections in a regulated audit context are not simple edits — they're material adjustments that require documented justification, a second approval, and potentially a note in the final submission. Building this correctly means:
- A supervisor role with unlock permissions
- A mandatory correction reason field
- Notifications to the original approver
- A clear display of "this record was unlocked and re-approved" in the audit trail

The current model is the safer baseline: lock first, build the unlock workflow with proper stakeholder input about what the approval chain should look like. Shipping a half-implemented unlock that an analyst could misuse is worse than no unlock at all.

**Workaround available today:** A Django admin user can directly modify `locked_for_audit` in the admin panel, which creates an escape hatch for the prototype without encoding a permissive workflow into the product.

---

## 3. Scope 3 Category 1 — Purchased goods and services from SAP procurement

The SAP parser only handles movement types 201 and 261 (fuel/material consumption). SAP MM also contains the purchase order and goods receipt data that would feed Scope 3 Category 1 (Purchased goods and services) — often the largest Scope 3 category for a manufacturing company.

**What this means:** The app handles fuel (Scope 1), electricity (Scope 2), and business travel (Scope 3 Cat 6), but not supply chain emissions.

**Why I didn't build it:**

Scope 3 Category 1 is a genuinely hard problem:

1. **Material-to-category mapping:** SAP material numbers (MATNR) are client-defined strings like `100000023`. Without a client-specific lookup table mapping each material to an emission factor category (steel, plastics, services, etc.), you can't assign emission factors.

2. **Spend-based vs. activity-based factors:** Most companies start with spend-based emission factors ($ spent × kg CO₂e per $). These are available from databases like EEIO (US) or Exiobase (Europe). Activity-based factors (kg of steel × kg CO₂e per kg) are more accurate but require material quantity data and supplier-specific factors, which most SME suppliers can't provide.

3. **Double-counting risk:** Scope 3 Cat 1 and Scope 3 Cat 4 (Upstream transportation) can overlap with Scope 1 data from the same SAP system. You need explicit boundary rules.

The right way to handle this is a separate scoping conversation with the client and PM about which Scope 3 categories are in scope for this reporting period, what methodology they're using, and what supplier data is available. That conversation takes longer than 4 days to resolve correctly.

**What would need to be true to build this:** A material master export (MM60 or similar) mapping MATNR to category, plus agreement on whether to use spend-based or activity-based factors.
