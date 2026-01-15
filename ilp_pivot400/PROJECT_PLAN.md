PROJECT PLAN

1. Goal
This is a toy workshop.
I am trying to use Integer Linear Programming (ILP) to plan sectors for a centre pivot irrigated field under sector-control Variable Rate Irrigation (VRI).
After obtaining the optimum sector division, I will draw an irrigation map based on the sector division in ArcGIS Pro.

2. Context
I created a fishnet polygon called Pivot_400m_fishnet that covers a New Zealand farm pivot in ArcGIS Pro 3.6.0.
2.1 Information about Pivot_400m_fishnet
2.1.1 Projected Coordinate System
    - NZGD 2000 New Zealand Transverse Mercator (NZTM)
2.1.2 Pivot extent (m)
    - Top: 5,172,913.970500
    - Bottom: 5,172,113.970500
    - Left: 1,526,214.086700
    - Right: 1,527,014.086700
2.1.3 Pivot centre (m)
    - x0 = 1,526,614.0867 (POINT_X)
    - y0 = 5,172,513.9705 (POINT_Y)
2.1.4 Fishnet resolution and data storage
    - Pivot_400m_fishnet contains 5,024 cells (nominally 10 m x 10 m each).
    - Data is stored in: "D:\PythonLab\ilp_pivot400\Pivot_400m_Table.csv"
    - Calculated columns (bearing convention: 0 deg = North, clockwise positive):
      - dx = centroid_x - 1,526,614.0867
      - dy = centroid_y - 5,172,513.9705
      - bearing = (degrees(atan2(dx, dy)) + 360) % 360
      - ds_id = int(bearing) in {0..359}
    - In my case, every cell area is exactly 100 m2.
    - Always use Shape_Area (m2) as the authoritative area for aggregation and water budgeting.

2.2 Field and soil description
2.2.1 The pivot field is heterogeneous with 5 conceptual soil types:
    - Deep silt loam Silt loam
    - Shallow stony Sandy loam
    - Gravelly Loamy sand
    - Compacted Clay loam
    - Organic patch Silt loam
    - Note: Soil types are simulation-only unless explicitly joined for visualization. soil_type is only used upstream to generate Y_j(k)/profit, which then drives the ILP and the final irrigation map, i.e. soil_type -> WPF -> Yield_j(k)/Profit_j(k) -> ILP solution (assigned IW per DS) -> sector map.
    - Explicitly state that `soil_type` stays in the table unless you choose to join it into the feature class for visualization.
2.2.2 Dominant forage:
    - Perennial ryegrass (Lolium perenne) with white clover (Trifolium repens).
    - Parameter    Typical value
    - Rooting depth (effective)    0.6-0.8 m
    - Crop coefficient (Kc)    0.95-1.15 (seasonal)
    - Depletion fraction (p)    ~0.45
    - Growth response    Concave to water deficit
2.2.3 Cost parameter ranges:
    - "price_per_t": 300.0,
    - "water_cost_per_mm_ha": 2.25,
    - Note:
      "price_per_t_range": [250.0, 350.0], "water_cost_per_mm_ha_range": [1.5, 3.0], and
      "profit_rate_per_ha_range": [120.0, 520.0] are for reference in the future.
      Profit per ha (same yield/IW ranges): roughly 120-520 $/ha, with the low end dipping near zero or slightly negative if you irrigate heavily on very low-responding soils.

3. Next Steps
3.1 Data and Optimisation Preparation
3.1.1 Discrete irrigation levels (the k set)
    - Candidate irrigation water (IW) levels:
      - K = {0, 10, 20, ..., 100} mm
    - Notes:
      - Treat IW as a cumulative irrigation depth (mm) applied over the sector area throughout a peak-demand decision window (roughly 3 weeks).
      - Volume is derived from mm x area (1 mm over 1 m2 = 0.001 m3).
3.1.2 Create the missing core data product: yield response versus IW
    - Assign each conceptual soil type a simple parametric water production function (WPF) with a concave, saturating response to IW (synthetic WPF for proof-of-concept).
    - For each cell c, compute yield y_c(k) from its soil type and IW level k.
    - Aggregate to degree-slice (DS) responses for each j and k using Shape_Area weighting.
    - Explicitly store:
      - y_c(k) (optional, if needed)
      - Y_j(k) and Area_j (required)
      - Profit_j(k) (required for optimisation)
3.1.3 Optimisation objective and units (profit accounting)
    - Objective:
      - Maximise total profit over the pivot (per optimisation window).
    - Per degree-slice j and irrigation level k (per-area accounting):
      - YieldRate_j(k): t/ha (use Y_j(k) expressed as t/ha)
      - Price: $/t
      - IW_k: mm
      - WaterCost: $/(mm*ha)
    - ProfitRate_j(k) [$ / ha] = Price * YieldRate_j(k) - WaterCost * IW_k
    - Convert to total profit for DS j for use in ILP sums:
      - area_j_ha = Area_j_m2 / 10,000
      - Profit_j(k) [$] = ProfitRate_j(k) * area_j_ha
    - Keep the yield unit explicit as t DM/ha per ~3-week window to avoid misinterpretation.

3.2 Candidate Arc-Sectors
3.2.1 Definitions and notation
    - Cell c:
      A fishnet polygon (nominally 10 m x 10 m). Each cell has:
        - ds_id in {0..359}
        - Shape_Area_c (m2)
        - conceptual soil type
    - Degree-slice j (DS j):
      The atomic 1-degree angular unit, j = 0..359.
      DS j consists of all cells with ds_id = j.
      For each DS j and irrigation water (IW) level k:
        - Predict cell yields under IW = k for all cells in DS j: y_c(k)
        - Aggregate to obtain DS yield response Y_j(k) using area weighting:
          Y_j(k) = (sum over c in DS j of y_c(k) * Area_c) / (sum over c in DS j of Area_c)
        - DS area:
          Area_j = sum over c in DS j of Area_c
      DS optimum (diagnostic only; ILP will choose k globally under constraints):
        - IW*_j = argmax_k Y_j(k)
        - y*_j = max_k Y_j(k)
    - Note: ds_id = int(bearing) is sensitive at exact integer-degree boundaries; ensure GIS and scripts use the same bearing convention and clamp 360 deg to 0.
    - Candidate arc-sector i (AS i):
      A contiguous set of degree-slices defined by:
        - start angle: s(i) in {0..359}
        - length: L(i) in degrees, with L(i) >= Lmin
        - wrap-around allowed (circular indexing on 0..359)
      Interpretation:
        - All degree-slices inside AS i receive the same IW = k.
      For each candidate arc-sector i and IW level k:
        - Aggregate DS responses inside AS i at the same k -> Y_i(k)
        - Sector area:
          Area_i = sum over j in AS i of Area_j
      Arc-sector optimum (diagnostic only):
        - IW*(i) = argmax_k Y_i(k)
        - y(i) = max_k Y_i(k)
    - Selected arc-sectors:
      Chosen candidate arc-sectors (x(i,k) = 1).
      Maximum number allowed: Pmax.
3.2.2 Build candidate arc-sectors (the AS library) and their aggregated responses
    - Define each candidate arc-sector i as a contiguous set of degree-slices with:
      - start angle s(i) in {0..359}
      - length L(i) in {Lmin..Lmax}
      - wrap-around allowed (circular indexing)
3.2.3 Degree-slice set completeness (and how to handle empty slices)
    - Use the full set of degree-slices:
      - J = {0, 1, ..., 359}
    - If some ds_id have zero cells due to discretisation:
      - Preferably: adjust the GIS pre-processing so every ds_id has non-zero area (recommended for final mapping).
      - If keeping empty ds_id for clean circular logic (prototype stage):
        - Area_j = 0
        - Profit_j(k) = 0 for all k
        - Note: this can slightly distort sector geometry feasibility if many ds_id are empty.
3.2.4 Feasibility conditions (coverage with sector length bounds)
    - To cover the full 360 degrees with at most Pmax sectors of lengths in [Lmin, Lmax], ensure feasibility by checking:
      - There exists an integer p in {1..Pmax} such that:
        p * Lmin <= 360 <= p * Lmax
3.2.5 Enumeration of candidate arc-sectors
    - For each start angle s = 0..359:
      - For each length L = Lmin..Lmax:
        - Create candidate sector i = (s, L) with wrap-around allowed.
    - Example parameters:
      - Lmin = 5 degrees
      - Lmax = 120 degrees
    - PLUS include ONE special candidate for L = 360 degrees (single full-circle sector; do not duplicate for every start angle).
      Where:
      If Lmax < 360: enumerate Lmin..Lmax for every start, and add one special full-circle candidate (start=0, L=360).
      If Lmax >= 360: exclude L=360 from the per-start loop and add one special full-circle candidate (start=0, L=360).
    - Notes:
      - Candidate count (excluding IW levels) is:
        N_candidates = 360 * (Lmax - Lmin + 1) + 1
        Example: Lmin=5, Lmax=120 -> 360*(116)+1 = 41,761 candidates.
      - With |K| irrigation levels, binary variables scale as:
        N_x = N_candidates * |K|
        Example: 41,761 * 11 ~= 459,371 binaries.
3.2.6 Arc-sector profit under each IW level
    - For each candidate arc-sector i and IW level k:
      - Aggregate DS profits within i:
        Profit_i(k) = sum over j in AS i of Profit_j(k)
    - Also compute sector area for water budgeting:
      - Area_i = sum over j in AS i of Area_j
3.3 ILP Formulation (Arc-Sector Library Approach)
3.3.1 Decision variables
    - x(i,k) in {0,1}
      x(i,k) = 1 means: "select arc-sector i and assign IW level k to it".
3.3.2 Objective
    - Maximise (with optional sector-count penalty as a cost):
      Maximise:
      sum over (i,k) [ Profit_i(k) * x(i,k) ]
        - SectorPenalty * sum over (i,k) x(i,k)
      Where:
        - SectorPenalty has units of $ per sector (per optimisation window).
        - If you already enforce a hard Pmax, SectorPenalty is optional (use it only if you want the model to prefer fewer sectors even when more are allowed).
3.3.3 Constraints
    - (a) Coverage (exact partition of the 360 degrees)
      For every degree-slice j in 0..359:
        - sum over (i,k) such that j is inside arc-sector i of x(i,k) = 1
    - (b) Maximum number of sectors (hard cap)
      - sum over (i,k) x(i,k) <= Pmax
    - (c) Water budget constraint (hard constraint; volume form)
      Given:
        - TotalDepthBudget = 80 mm over the 3-week window
        - Pivot area = 502,400 m2, so 1 mm = 502.4 m3
        - TotalWaterBudget = 80 x 502.4 = 40,192 m3
      Constraint:
        - sum over (i,k) [ WaterApplied_i(k) * x(i,k) ] <= 40,192
      Where:
        - WaterApplied_i(k) [m3] = (IW_k [mm] * Area_i [m2]) / 1000
        - Water budget uses a fixed pivot area of 502,400 m2; if the sum of Shape_Area differs, the constraint should use the computed total area.
        - Note whether the water budget should use the summed `Shape_Area` from the table rather than the fixed 502,400 m2 if they differ.
3.4 Solve the ILP
3.4.1 Solver options (Python)
    - OR-Tools: SCIP
    - Implementation note:
      - This is a set-partitioning model; if runtime becomes an issue, solver choice matters (SCIP often performs better than CBC on harder MILPs).
3.4.2 Deliverables from the solver
    - Derive for each degree-slice j:
      - assigned_IW (k)
      - sector_id (post-processed by grouping contiguous DS with identical assignment, and handling wrap-around)
      - derived sector start angle and length
3.5 Push the solution back into ArcGIS Pro to create the irrigation map
3.5.1 Create a DS result table with 360 rows (j = 0..359) containing:
    - ds_id (j)
    - sector_id
    - assigned_IW
3.5.2 Join the DS result table to the fishnet feature class using ds_id / zone_id.
    - Confirm the join key names in ArcGIS (`OBJECTID` vs `zone_id`) so the DS results table links cleanly.
3.5.3 Add/confirm fields on the fishnet:
    - sector_id
    - IW (assigned_IW)
3.5.4 Dissolve fishnet polygons
    - Dissolve by sector_id
    - Optionally dissolve by (sector_id, IW) if you want polygons guaranteed to be uniform in IW
3.5.5 Symbolise output polygons by IW to produce the final irrigation map
3.6 Validate the result
3.6.1 Minimum validation
    - Compare against baseline uniform irrigation:
      - same total water volume (preferred if you enforce a budget), or
      - same average IW depth over the pivot
3.6.2 Report at least
    - Total profit ($)
    - Number of sectors used
    - Distribution / histogram of sector lengths (degrees)
    - Total water applied (m3) and average IW (mm)
    - (Optional) Profit gain vs baseline (%)
3.6.3 Sensitivity analysis
    - Rerun for different Pmax values
    - Rerun for different Lmin values
      Observe stability in:
      - profit
      - sector count
      - sector geometry / spatial patterns
      - assigned IW distribution
