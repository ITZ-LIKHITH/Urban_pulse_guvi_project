-- =====================================================================
-- URBAN PULSE: Citizen Complaint Intelligence & Resolution Analytics
-- 15 Core Analyst SQL Investigations
-- Target Database: urban_pulse_db
-- Target Table: service_requests
-- =====================================================================

USE urban_pulse_db;

-- ---------------------------------------------------------------------
-- Task 1: Total Distinct Request Volume
-- Business Question: What is the total volume of distinct service requests handled by the 311 system?
-- Analytical Goal: Establish baseline volume and ensure identifier uniqueness.
-- ---------------------------------------------------------------------
SELECT 
    COUNT(DISTINCT unique_key) AS total_distinct_requests,
    MIN(created_date) AS earliest_request_date,
    MAX(created_date) AS latest_request_date,
    COUNT(DISTINCT agency) AS active_agencies,
    COUNT(DISTINCT complaint_type) AS distinct_complaint_types
FROM service_requests;


-- ---------------------------------------------------------------------
-- Task 2: Top 10 Complaint Categories by Count
-- Business Question: What are the most frequent citizen complaint categories?
-- Analytical Goal: Identify primary drivers of public inquiry to prioritize municipal resources.
-- ---------------------------------------------------------------------
SELECT 
    complaint_type,
    COUNT(*) AS total_complaints,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS percentage_of_total
FROM service_requests
GROUP BY complaint_type
ORDER BY total_complaints DESC
LIMIT 10;


-- ---------------------------------------------------------------------
-- Task 3: Agency Workload Distribution
-- Business Question: How is the service request workload distributed across municipal agencies?
-- Analytical Goal: Understand administrative burden and departmental operational focus.
-- ---------------------------------------------------------------------
SELECT 
    agency,
    MAX(agency_name) AS agency_name,
    COUNT(*) AS total_requests,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS workload_share_pct,
    COUNT(DISTINCT complaint_type) AS distinct_complaints_handled
FROM service_requests
GROUP BY agency
ORDER BY total_requests DESC;


-- ---------------------------------------------------------------------
-- Task 4: Request Volume by Borough
-- Business Question: How does complaint volume vary across New York City's five boroughs?
-- Analytical Goal: Detect geographic variations and identify areas with high demand density.
-- ---------------------------------------------------------------------
SELECT 
    borough,
    COUNT(*) AS total_requests,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS borough_share_pct,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS volume_rank
FROM service_requests
GROUP BY borough
ORDER BY total_requests DESC;


-- ---------------------------------------------------------------------
-- Task 5: Monthly Request Trend
-- Business Question: What is the historical trajectory and seasonality of complaint volumes?
-- Analytical Goal: Identify peak operating months to guide seasonal staffing and budget planning.
-- ---------------------------------------------------------------------
SELECT 
    created_year,
    created_month,
    MAX(created_month_name) AS month_name,
    COUNT(*) AS total_requests,
    LAG(COUNT(*)) OVER (ORDER BY created_year, created_month) AS previous_month_requests,
    ROUND(
        (COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY created_year, created_month)) * 100.0 / 
        NULLIF(LAG(COUNT(*)) OVER (ORDER BY created_year, created_month), 0), 
        2
    ) AS month_over_month_pct_change
FROM service_requests
WHERE created_year IS NOT NULL AND created_month IS NOT NULL
GROUP BY created_year, created_month
ORDER BY created_year, created_month;


-- ---------------------------------------------------------------------
-- Task 6: Demand by Weekday and Hour
-- Business Question: What are the peak days of the week and hours of the day for incoming complaints?
-- Analytical Goal: Inform shift scheduling, 311 call center staffing, and field response rotas.
-- ---------------------------------------------------------------------
-- 6A: Volume by Weekday
SELECT 
    created_weekday,
    COUNT(*) AS total_requests,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS weekday_share_pct
FROM service_requests
WHERE created_weekday IS NOT NULL
GROUP BY created_weekday
ORDER BY FIELD(created_weekday, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');

-- 6B: Volume by Hour of Day
SELECT 
    created_hour,
    COUNT(*) AS total_requests,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS hourly_share_pct
FROM service_requests
WHERE created_hour IS NOT NULL
GROUP BY created_hour
ORDER BY created_hour;


-- ---------------------------------------------------------------------
-- Task 7: Distribution of Recorded Request Statuses
-- Business Question: What proportion of requests are recorded as Closed vs. In Progress or Open?
-- Analytical Goal: Assess ticket progression and identify potential administrative backlogs.
-- ---------------------------------------------------------------------
SELECT 
    status,
    COUNT(*) AS count_of_requests,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS percentage_of_total,
    CASE 
        WHEN status = 'Closed' THEN 'Resolved Lifecycle'
        ELSE 'Active/Pending Lifecycle'
    END AS operational_category
FROM service_requests
GROUP BY status
ORDER BY count_of_requests DESC;


-- ---------------------------------------------------------------------
-- Task 8: Descriptive Statistics for Valid Resolution Durations
-- Business Question: What are the central tendency, spread, and extremes of resolution times?
-- Analytical Goal: Establish statistical benchmarks for civic service closure speeds.
-- ---------------------------------------------------------------------
SELECT 
    COUNT(*) AS valid_closed_cases,
    ROUND(AVG(resolution_hours), 2) AS mean_resolution_hours,
    ROUND(STDDEV(resolution_hours), 2) AS std_resolution_hours,
    ROUND(MIN(resolution_hours), 2) AS min_resolution_hours,
    ROUND(MAX(resolution_hours), 2) AS max_resolution_hours,
    ROUND(VARIANCE(resolution_hours), 2) AS variance_resolution_hours
FROM service_requests
WHERE is_valid_resolution = TRUE;


-- ---------------------------------------------------------------------
-- Task 9: Median Resolution Duration by Complaint Category
-- Business Question: Which complaint types take the longest (and shortest) median time to resolve?
-- Analytical Goal: Highlight issue complexity (median is preferred over mean due to right-skew).
-- ---------------------------------------------------------------------
WITH RankedDurations AS (
    SELECT 
        complaint_type,
        resolution_hours,
        ROW_NUMBER() OVER (PARTITION BY complaint_type ORDER BY resolution_hours) AS row_num,
        COUNT(*) OVER (PARTITION BY complaint_type) AS total_count
    FROM service_requests
    WHERE is_valid_resolution = TRUE
)
SELECT 
    complaint_type,
    total_count AS closed_case_volume,
    ROUND(AVG(resolution_hours), 2) AS median_resolution_hours
FROM RankedDurations
WHERE row_num IN (FLOOR((total_count + 1) / 2), CEIL((total_count + 1) / 2))
GROUP BY complaint_type, total_count
HAVING total_count >= 10
ORDER BY median_resolution_hours DESC
LIMIT 15;


-- ---------------------------------------------------------------------
-- Task 10: Median Resolution Duration by Agency
-- Business Question: How do median resolution durations compare across city agencies?
-- Analytical Goal: Compare departmental service turnaround while accounting for service complexity.
-- ---------------------------------------------------------------------
WITH AgencyRankedDurations AS (
    SELECT 
        agency,
        resolution_hours,
        ROW_NUMBER() OVER (PARTITION BY agency ORDER BY resolution_hours) AS row_num,
        COUNT(*) OVER (PARTITION BY agency) AS total_count
    FROM service_requests
    WHERE is_valid_resolution = TRUE
)
SELECT 
    agency,
    total_count AS closed_cases_handled,
    ROUND(AVG(resolution_hours), 2) AS median_resolution_hours
FROM AgencyRankedDurations
WHERE row_num IN (FLOOR((total_count + 1) / 2), CEIL((total_count + 1) / 2))
GROUP BY agency, total_count
ORDER BY median_resolution_hours DESC;


-- ---------------------------------------------------------------------
-- Task 11: IQR-Based Outlier Investigation
-- Business Question: How many requests exhibit extreme resolution durations based on IQR bounds?
-- Analytical Goal: Screen long-tail cases that deviate substantially from typical service patterns.
-- ---------------------------------------------------------------------
WITH RankedRows AS (
    SELECT 
        resolution_hours,
        ROW_NUMBER() OVER (ORDER BY resolution_hours) AS row_num,
        COUNT(*) OVER () AS n_count
    FROM service_requests
    WHERE is_valid_resolution = TRUE
),
Percentiles AS (
    -- Matches pandas linear interpolation method: Q = val(k) + (val(k+1) - val(k)) * fraction
    -- Uses MAX(n_count) to strictly comply with MySQL ONLY_FULL_GROUP_BY mode
    SELECT 
        ROUND(
            MAX(CASE WHEN row_num = FLOOR(1 + 0.25 * (n_count - 1)) THEN resolution_hours END) * (1.0 - (0.25 * (MAX(n_count) - 1) - FLOOR(0.25 * (MAX(n_count) - 1))))
            + MAX(CASE WHEN row_num = FLOOR(1 + 0.25 * (n_count - 1)) + 1 THEN resolution_hours END) * (0.25 * (MAX(n_count) - 1) - FLOOR(0.25 * (MAX(n_count) - 1))),
            2
        ) AS q1,
        ROUND(
            MAX(CASE WHEN row_num = FLOOR(1 + 0.75 * (n_count - 1)) THEN resolution_hours END) * (1.0 - (0.75 * (MAX(n_count) - 1) - FLOOR(0.75 * (MAX(n_count) - 1))))
            + MAX(CASE WHEN row_num = FLOOR(1 + 0.75 * (n_count - 1)) + 1 THEN resolution_hours END) * (0.75 * (MAX(n_count) - 1) - FLOOR(0.75 * (MAX(n_count) - 1))),
            2
        ) AS q3
    FROM RankedRows
),
Thresholds AS (
    SELECT 
        q1, 
        q3, 
        ROUND(q3 - q1, 2) AS iqr,
        ROUND(GREATEST(0, q1 - 1.5 * (q3 - q1)), 2) AS lower_cutoff,
        ROUND(q3 + 1.5 * (q3 - q1), 2) AS upper_cutoff
    FROM Percentiles
)
SELECT 
    t.q1,
    t.q3,
    t.iqr,
    t.lower_cutoff,
    t.upper_cutoff,
    COUNT(s.unique_key) AS total_outlier_requests,
    ROUND(COUNT(s.unique_key) * 100.0 / (SELECT COUNT(*) FROM service_requests WHERE is_valid_resolution = TRUE), 2) AS outlier_pct_of_valid,
    ROUND(MIN(s.resolution_hours), 2) AS min_outlier_hours,
    ROUND(MAX(s.resolution_hours), 2) AS max_outlier_hours,
    ROUND(AVG(s.resolution_hours), 2) AS avg_outlier_hours
FROM Thresholds t
JOIN service_requests s ON s.is_valid_resolution = TRUE 
   AND (s.resolution_hours < t.lower_cutoff OR s.resolution_hours > t.upper_cutoff)
GROUP BY t.q1, t.q3, t.iqr, t.lower_cutoff, t.upper_cutoff;


-- ---------------------------------------------------------------------
-- Task 12: Resolution-Time Skewness and Distribution Bins
-- Business Question: How are resolution times distributed across operational time buckets?
-- Analytical Goal: Quantify heavy-tailed skewness and operational turnaround brackets.
-- ---------------------------------------------------------------------
SELECT 
    CASE 
        WHEN resolution_hours <= 12 THEN '0 - 12 Hours (Rapid)'
        WHEN resolution_hours <= 24 THEN '12 - 24 Hours (Same Day/Next Day)'
        WHEN resolution_hours <= 72 THEN '24 - 72 Hours (2-3 Days)'
        WHEN resolution_hours <= 168 THEN '72 - 168 Hours (Within 1 Week)'
        ELSE 'Over 168 Hours (> 1 Week)'
    END AS duration_bracket,
    COUNT(*) AS request_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests WHERE is_valid_resolution = TRUE), 2) AS percentage_of_valid
FROM service_requests
WHERE is_valid_resolution = TRUE
GROUP BY duration_bracket
ORDER BY MIN(resolution_hours);


-- ---------------------------------------------------------------------
-- Task 13: Geographic Complaint Concentration
-- Business Question: Which zip codes and borough corridors exhibit the highest complaint density?
-- Analytical Goal: Identify spatial hotspots for targeted municipal inspection and street-level teams.
-- ---------------------------------------------------------------------
SELECT 
    borough,
    incident_zip,
    COUNT(*) AS total_complaints,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM service_requests), 2) AS share_of_citywide_total
FROM service_requests
WHERE incident_zip IS NOT NULL AND incident_zip != '' AND borough != 'Unspecified'
GROUP BY borough, incident_zip
ORDER BY total_complaints DESC
LIMIT 15;


-- ---------------------------------------------------------------------
-- Task 14: Recorded Closure-Rate Comparison
-- Business Question: How does the recorded closure percentage vary by agency?
-- Analytical Goal: Monitor ticketing lifecycle closure efficiency across departments.
-- ---------------------------------------------------------------------
SELECT 
    agency,
    COUNT(*) AS total_assigned_requests,
    SUM(CASE WHEN is_closed = TRUE THEN 1 ELSE 0 END) AS closed_requests,
    SUM(CASE WHEN is_closed = FALSE THEN 1 ELSE 0 END) AS open_or_pending_requests,
    ROUND(SUM(CASE WHEN is_closed = TRUE THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS recorded_closure_rate_pct
FROM service_requests
GROUP BY agency
ORDER BY recorded_closure_rate_pct DESC;


-- ---------------------------------------------------------------------
-- Task 15: Categories with Both High Request Volume and Long Median Resolution Duration
-- Business Question: Which complaint categories exhibit both heavy public demand and slow turnaround?
-- Analytical Goal: Prioritize critical civic bottlenecks that impact large numbers of citizens using median duration.
-- ---------------------------------------------------------------------
WITH RankedPerCategory AS (
    SELECT 
        complaint_type,
        agency,
        resolution_hours,
        ROW_NUMBER() OVER (PARTITION BY complaint_type, agency ORDER BY resolution_hours) AS row_num,
        COUNT(*) OVER (PARTITION BY complaint_type, agency) AS cat_volume
    FROM service_requests
    WHERE is_valid_resolution = TRUE
),
CategoryMedians AS (
    SELECT 
        complaint_type,
        agency,
        cat_volume AS total_requests,
        ROUND(AVG(resolution_hours), 2) AS median_resolution_hours
    FROM RankedPerCategory
    WHERE row_num IN (FLOOR((cat_volume + 1) / 2), CEIL((cat_volume + 1) / 2))
    GROUP BY complaint_type, agency, cat_volume
),
CitywideBenchmark AS (
    SELECT 
        AVG(total_requests) AS avg_volume_cutoff
    FROM CategoryMedians
),
CitywideMedianRes AS (
    SELECT ROUND(AVG(resolution_hours), 2) AS citywide_median_hours
    FROM (
        SELECT resolution_hours,
               ROW_NUMBER() OVER (ORDER BY resolution_hours) AS rn,
               COUNT(*) OVER () AS cnt
        FROM service_requests
        WHERE is_valid_resolution = TRUE
    ) t
    WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
)
SELECT 
    cm.complaint_type,
    cm.agency,
    cm.total_requests,
    cm.median_resolution_hours,
    'Critical Operational Bottleneck' AS classification
FROM CategoryMedians cm
CROSS JOIN CitywideBenchmark cb
CROSS JOIN CitywideMedianRes cmr
WHERE cm.total_requests >= cb.avg_volume_cutoff
  AND cm.median_resolution_hours >= cmr.citywide_median_hours
ORDER BY cm.total_requests DESC, cm.median_resolution_hours DESC;

