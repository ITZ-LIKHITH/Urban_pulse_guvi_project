# URBAN PULSE: Data Cleaning and Validation Log

## 1. Executive Summary
- **Source Extract Count**: 100,000
- **Cleaned Dataset Count**: 100,000
- **Recorded Closed Requests**: 98,392 (98.39%)
- **Open / In-Progress Requests**: 1,608 (1.61%)
- **Deduplicated Identifiers**: 0
- **Coordinate Anomalies Flagged**: 0
- **Negative Resolution Durations Flagged**: 137

## 2. Statistical Distribution of Resolution Duration
- **Valid Resolution Cases**: 98,255
- **Mean Duration**: 379.42 hours
- **Median Duration**: 2.92 hours
- **Standard Deviation**: 2018.25 hours
- **Distribution Skewness**: 10.124 (Heavy right-tail)
- **Q1 (25th percentile)**: 0.63 hours
- **Q3 (75th percentile)**: 56.8 hours
- **IQR (Interquartile Range)**: 56.16 hours
- **IQR Outlier Upper Threshold**: 141.04 hours
- **Identified Outliers**: 16636 (16.93% of valid cases)

## 3. Transformations Applied
- Removed 0 duplicate or null unique_keys
- Standardized borough names casing while preserving genuine missing values
- Parsed created_date, closed_date, due_date directly as local timestamps (no UTC shift)
- Flagged and nulled 0 out-of-bounds geographic coordinates
- Detected and nulled 137 negative resolution duration anomalies

## 4. Responsible Interpretation Caveats
1. **Reported Requests vs. Reality**: NYC 311 captures citizen reports, which correlate with civic engagement, digital access, and awareness, not solely underlying physical problem frequency.
2. **Recorded Closure != Citizen Satisfaction**: Closure reflects internal departmental ticket completion status.
3. **Outliers as Operational Prompts**: Extreme resolution durations are flagged for qualitative review, not deleted, as complex municipal interventions legitimately require extensive lead times.
