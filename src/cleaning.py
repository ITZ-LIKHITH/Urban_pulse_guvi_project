"""
URBAN PULSE: Citizen Complaint Intelligence & Resolution Analytics
Module: Data Cleaning, Quality Validation & Feature Engineering Pipeline
Author: Urban Pulse Analytics Team
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any


def load_raw_data(filepath: str = "data/raw_data.csv") -> pd.DataFrame:
    """Load raw NYC 311 service request dataset."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Raw data file not found at: {filepath}")
    
    print(f"[STEP 1] Loading raw dataset from '{filepath}'...")
    df = pd.read_csv(filepath, low_memory=False)
    print(f"         Loaded {len(df):,} rows and {len(df.columns)} columns.")
    return df


def inspect_raw_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Inspect initial dimensions, missingness, and duplicates."""
    inspection = {
        "initial_rows": int(len(df)),
        "initial_columns": int(len(df.columns)),
        "total_missing_cells": int(df.isnull().sum().sum()),
        "columns_with_nulls": {col: int(cnt) for col, cnt in df.isnull().sum().items() if cnt > 0},
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_unique_keys": int(df["unique_key"].duplicated().sum()) if "unique_key" in df.columns else 0,
    }
    print(f"[STEP 2] Raw Inspection Summary:")
    print(f"         - Total rows: {inspection['initial_rows']:,}")
    print(f"         - Duplicate unique keys: {inspection['duplicate_unique_keys']}")
    print(f"         - Total missing values: {inspection['total_missing_cells']:,}")
    return inspection


def clean_and_transform(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """
    Execute full cleaning, normalization, validation, and feature engineering.
    Returns:
        (cleaned_df, cleaning_log, outliers_df)
    """
    df = df_raw.copy()
    cleaning_log: Dict[str, Any] = {
        "raw_record_count": len(df),
        "deduplicated_count": 0,
        "invalid_dates_flagged": 0,
        "negative_duration_flagged": 0,
        "coordinate_anomalies_flagged": 0,
        "transformations_applied": [],
    }

    # 1. Deduplicate by unique_key
    if "unique_key" in df.columns:
        initial_count = len(df)
        df["unique_key"] = pd.to_numeric(df["unique_key"], errors="coerce")
        df = df.dropna(subset=["unique_key"])
        df["unique_key"] = df["unique_key"].astype(np.int64)
        df = df.drop_duplicates(subset=["unique_key"], keep="first")
        removed_dups = initial_count - len(df)
        cleaning_log["deduplicated_count"] = removed_dups
        cleaning_log["transformations_applied"].append(f"Removed {removed_dups} duplicate or null unique_keys")

    # Ensure all canonical schema columns exist in DataFrame (missing columns set to np.nan, preserving genuine missingness)
    canonical_schema_cols = [
        "descriptor_2", "resolution_description", "community_board",
        "council_district", "police_precinct", "open_data_channel_type", "park_borough"
    ]
    for col in canonical_schema_cols:
        if col not in df.columns:
            df[col] = pd.Series([np.nan] * len(df), dtype=object)

    # 2. Text Normalization - trim whitespace on valid text, preserve genuine missing values (do NOT fill with fake 'Unknown' or 'Unspecified')
    text_cols = [
        "agency", "agency_name", "complaint_type", "descriptor", "descriptor_2",
        "location_type", "incident_address", "street_name", "city", "borough",
        "status", "resolution_description", "community_board", "council_district",
        "police_precinct", "open_data_channel_type", "park_borough"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(object)
            mask_valid = df[col].notna() & (~df[col].astype(str).str.strip().isin(["nan", "None", "NULL", "", "N/A", "<NA>"]))
            clean_series = pd.Series(np.nan, index=df.index, dtype=object)
            clean_series[mask_valid] = df.loc[mask_valid, col].astype(str).str.strip()
            df[col] = clean_series

    # Standardize Borough names casing if present, without replacing genuine missing values
    if "borough" in df.columns:
        borough_map = {
            "BRONX": "BRONX",
            "BROOKLYN": "BROOKLYN",
            "MANHATTAN": "MANHATTAN",
            "QUEENS": "QUEENS",
            "STATEN ISLAND": "STATEN ISLAND",
            "STATEN IS": "STATEN ISLAND",
            "UNSPECIFIED": "Unspecified",
        }
        valid_b = df["borough"].notna()
        df.loc[valid_b, "borough"] = df.loc[valid_b, "borough"].astype(str).str.upper().map(lambda b: borough_map.get(b, b))
        cleaning_log["transformations_applied"].append("Standardized borough names casing while preserving genuine missing values")

    # 3. Parse Datetime Fields (NYC Open Data floating timestamps are already local time)
    datetime_cols = ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]
    for col in datetime_cols:
        if col in df.columns:
            # Strip any trailing 'Z' or timezone offsets to guarantee preservation of original NYC local clock time
            # NYC Open Data floating timestamps represent local wall-clock time in America/New_York
            s = df[col].astype(str).str.strip().str.replace(r"[Zz]$", "", regex=True)
            df[col] = pd.to_datetime(s, errors="coerce")
            if hasattr(df[col].dt, "tz") and df[col].dt.tz is not None:
                df[col] = df[col].dt.tz_localize(None)

    cleaning_log["transformations_applied"].append("Parsed created_date, closed_date, due_date directly as local timestamps (no UTC shift)")

    # 4. Clean Numeric and Coordinate Columns
    coord_cols = ["latitude", "longitude", "incident_zip"]
    for col in coord_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Flag invalid coordinates outside New York City metro bounds
    # NYC lat: [40.40, 41.10], lon: [-74.35, -73.65]
    if "latitude" in df.columns and "longitude" in df.columns:
        invalid_coords = (
            (df["latitude"].notna() & ~df["latitude"].between(40.40, 41.10)) |
            (df["longitude"].notna() & ~df["longitude"].between(-74.35, -73.65))
        )
        coord_anomalies = int(invalid_coords.sum())
        cleaning_log["coordinate_anomalies_flagged"] = coord_anomalies
        # Null out impossible coordinates rather than silently keeping corrupt spatial data
        df.loc[invalid_coords, ["latitude", "longitude"]] = np.nan
        cleaning_log["transformations_applied"].append(f"Flagged and nulled {coord_anomalies} out-of-bounds geographic coordinates")

    # 5. Feature Engineering: Resolution Duration & Temporal Columns
    # Closure indicator
    df["is_closed"] = df["closed_date"].notna()

    # Resolution duration in hours: (closed_date - created_date)
    duration_seconds = (df["closed_date"] - df["created_date"]).dt.total_seconds()
    df["resolution_hours"] = duration_seconds / 3600.0

    # Data Quality Validation: Flag negative durations (closed before created)
    negative_mask = df["resolution_hours"] < 0
    neg_count = int(negative_mask.sum())
    cleaning_log["negative_duration_flagged"] = neg_count
    if neg_count > 0:
        print(f"[WARN] Found {neg_count} records with negative resolution hours (closed_date < created_date).")
        # Keep flag for auditability and set resolution_hours to NaN for analytical queries
        df.loc[negative_mask, "resolution_hours"] = np.nan
        cleaning_log["transformations_applied"].append(f"Detected and nulled {neg_count} negative resolution duration anomalies")

    # Flag for valid resolution duration
    df["is_valid_resolution"] = df["resolution_hours"].notna() & (df["resolution_hours"] >= 0)

    # Resolution threshold categorization (Illustrative civic benchmark)
    def categorize_duration(hours):
        if pd.isna(hours) or hours < 0:
            return "Unresolved / Invalid"
        elif hours <= 24.0:
            return "Under 24 Hours"
        elif hours <= 72.0:
            return "24 to 72 Hours"
        else:
            return "Over 72 Hours"

    df["duration_category"] = df["resolution_hours"].apply(categorize_duration)

    # Temporal feature decomposition
    df["created_year"] = df["created_date"].dt.year
    df["created_month"] = df["created_date"].dt.month
    df["created_month_name"] = df["created_date"].dt.strftime("%B")
    df["created_weekday"] = df["created_date"].dt.day_name()
    df["created_hour"] = df["created_date"].dt.hour

    # 6. Statistical Checking & IQR Outlier Screening on Resolution Duration
    valid_res = df[df["is_valid_resolution"]]["resolution_hours"]
    if len(valid_res) > 0:
        q1 = float(valid_res.quantile(0.25))
        q3 = float(valid_res.quantile(0.75))
        iqr = q3 - q1
        lower_bound = max(0.0, q1 - 1.5 * iqr)
        upper_bound = q3 + 1.5 * iqr

        df["is_resolution_outlier"] = (
            df["is_valid_resolution"] &
            ((df["resolution_hours"] < lower_bound) | (df["resolution_hours"] > upper_bound))
        )
        outliers_df = df[df["is_resolution_outlier"]].copy()

        cleaning_log["iqr_statistics"] = {
            "valid_resolution_records": int(len(valid_res)),
            "mean_hours": round(float(valid_res.mean()), 2),
            "median_hours": round(float(valid_res.median()), 2),
            "std_hours": round(float(valid_res.std()), 2),
            "skewness": round(float(valid_res.skew()), 3),
            "q1_25th_percentile": round(q1, 2),
            "q3_75th_percentile": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
            "outlier_count": int(len(outliers_df)),
            "outlier_percentage": round(len(outliers_df) / len(valid_res) * 100, 2),
        }
    else:
        df["is_resolution_outlier"] = False
        outliers_df = pd.DataFrame()
        cleaning_log["iqr_statistics"] = {}

    cleaning_log["final_cleaned_count"] = len(df)
    cleaning_log["closed_records_count"] = int(df["is_closed"].sum())
    cleaning_log["open_records_count"] = int((~df["is_closed"]).sum())

    return df, cleaning_log, outliers_df


def generate_data_dictionary(df: pd.DataFrame) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate field-level data dictionary recording source name, meaning,
    data type, missingness, transformation, and analytical use.
    """
    descriptions = {
        "unique_key": ("Unique identifier assigned to each 311 service request", "Primary Key, distinct request counts"),
        "created_date": ("Date and time when the service request was submitted", "Temporal trend analysis, resolution calculation"),
        "closed_date": ("Date and time when the service request was officially marked closed", "Closure rate and resolution duration computation"),
        "due_date": ("Service level agreement date when action was expected", "SLA tracking and timeliness"),
        "resolution_action_updated_date": ("Date and time when resolution action was last recorded", "Agency responsiveness tracking"),
        "agency": ("Acronym of the responsible civic agency (e.g., NYPD, HPD, DSNY)", "Workload distribution, inter-agency resolution comparison"),
        "agency_name": ("Full formal title of the responsible municipal department", "Reporting and dashboard labels"),
        "complaint_type": ("Primary category classification of the service issue", "Complaint ranking, prioritization matrix, service mix"),
        "descriptor": ("Detailed specification of the complaint", "Root cause inspection, detailed filtering"),
        "descriptor_2": ("Secondary complaint descriptor or sub-category", "Sub-issue classification"),
        "location_type": ("Type of property or environment where the incident occurred", "Spatial vulnerability analysis"),
        "incident_zip": ("Five-digit postal zip code of the incident location", "Neighborhood-level aggregation"),
        "incident_address": ("Physical street number and name of the incident", "Micro-location investigations"),
        "street_name": ("Name of the street where incident occurred", "Corridor analysis"),
        "city": ("Municipality / borough neighborhood name", "Geographic filtering"),
        "status": ("Operational lifecycle state (Closed, In Progress, Open, Assigned)", "Status distribution, backlog tracking"),
        "resolution_description": ("Official explanation of agency findings and action taken", "Civic communication review, operational audit"),
        "community_board": ("NYC Community Board administrative district identifier", "Civic governance reporting"),
        "council_district": ("NYC City Council district identifier", "Policy and legislative resource allocation"),
        "police_precinct": ("NYPD police precinct jurisdiction", "Public safety coordination"),
        "borough": ("One of the five NYC boroughs or Unspecified", "Borough comparisons, geographic demand distribution"),
        "open_data_channel_type": ("Intake channel (PHONE, ONLINE, MOBILE, OTHER)", "Channel adoption and citizen contact preference"),
        "park_borough": ("Borough associated with park or public recreation facility", "Recreational infrastructure maintenance"),
        "latitude": ("WGS84 latitude coordinate in decimal degrees", "Geospatial mapping and clustering"),
        "longitude": ("WGS84 longitude coordinate in decimal degrees", "Geospatial mapping and clustering"),
        "resolution_hours": ("Derived elapsed time in hours between created_date and closed_date", "Core KPI, agency performance, IQR outlier detection"),
        "is_closed": ("Boolean flag: True if record has valid closed_date, False otherwise", "Closure rate calculation"),
        "is_valid_resolution": ("Boolean flag: True if resolution duration is non-negative and valid", "Valid sample filtering for statistical metrics"),
        "duration_category": ("Categorical bin: Under 24h, 24-72h, Over 72h, or Unresolved", "Operational tier analysis and SLA monitoring"),
        "created_year": ("Calendar year extracted from created_date", "Annual trend analysis"),
        "created_month": ("Calendar month number (1-12) extracted from created_date", "Seasonality analysis"),
        "created_month_name": ("Full month name (e.g. January, February) from created_date", "Dashboard monthly timeline visualization"),
        "created_weekday": ("Day of week (Monday-Sunday) from created_date", "Weekly demand patterning"),
        "created_hour": ("Hour of the day (0-23) from created_date", "Hourly peak load identification"),
        "is_resolution_outlier": ("Boolean flag: True if resolution_hours falls outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]", "Outlier screening and long-tail case investigation"),
    }

    records = []
    markdown_lines = [
        "# URBAN PULSE: Dataset Data Dictionary",
        "",
        "| Field Name | Data Type | Null Count | Null % | Meaning & Description | Transformation & Analytical Use |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for col in df.columns:
        dtype_str = str(df[col].dtype)
        null_count = int(df[col].isnull().sum())
        null_pct = round(null_count / len(df) * 100, 2)
        meaning, usage = descriptions.get(col, ("Dataset feature", "General exploration"))

        records.append({
            "field_name": col,
            "data_type": dtype_str,
            "null_count": null_count,
            "null_percentage": null_pct,
            "meaning": meaning,
            "analytical_use": usage,
        })

        markdown_lines.append(
            f"| `{col}` | `{dtype_str}` | {null_count:,} | {null_pct}% | {meaning} | {usage} |"
        )

    return "\n".join(markdown_lines), records


def run_pipeline(
    raw_path: str = "data/raw_data.csv",
    clean_path: str = "data/cleaned_data.csv",
    outlier_path: str = "data/resolution_outliers.csv",
    dict_doc_path: str = "docs/data_dictionary.md",
    dict_json_path: str = "data/data_dictionary.json",
    log_doc_path: str = "docs/cleaning_log.md",
    log_json_path: str = "data/cleaning_summary.json",
) -> pd.DataFrame:
    """Run end-to-end cleaning and documentation pipeline."""
    os.makedirs(os.path.dirname(clean_path), exist_ok=True)
    os.makedirs(os.path.dirname(dict_doc_path), exist_ok=True)

    print("==================================================")
    print("URBAN PULSE DATA CLEANING & VALIDATION PIPELINE")
    print("==================================================")

    # 1. Load raw data
    df_raw = load_raw_data(raw_path)

    # 2. Inspect raw data
    inspect_raw_data(df_raw)

    # 3. Clean and Transform
    print("\n[STEP 3] Executing transformations and quality checks...")
    df_clean, cleaning_log, outliers_df = clean_and_transform(df_raw)

    # 4. Save cleaned dataset
    df_clean.to_csv(clean_path, index=False)
    print(f"\n[STEP 4] Saved cleaned dataset to '{clean_path}' ({len(df_clean):,} records)")

    # 5. Save outliers
    outliers_df.to_csv(outlier_path, index=False)
    print(f"         Saved {len(outliers_df):,} outlier records to '{outlier_path}'")

    # 6. Generate and save Data Dictionary
    dict_md, dict_records = generate_data_dictionary(df_clean)
    with open(dict_doc_path, "w", encoding="utf-8") as f:
        f.write(dict_md)
    with open(dict_json_path, "w", encoding="utf-8") as f:
        json.dump(dict_records, f, indent=4)
    print(f"[STEP 5] Data dictionary saved to '{dict_doc_path}'")

    # 7. Generate and save Cleaning & Validation Log
    cleaning_md = f"""# URBAN PULSE: Data Cleaning and Validation Log

## 1. Executive Summary
- **Source Extract Count**: {cleaning_log['raw_record_count']:,}
- **Cleaned Dataset Count**: {cleaning_log['final_cleaned_count']:,}
- **Recorded Closed Requests**: {cleaning_log['closed_records_count']:,} ({cleaning_log['closed_records_count']/cleaning_log['final_cleaned_count']*100:.2f}%)
- **Open / In-Progress Requests**: {cleaning_log['open_records_count']:,} ({cleaning_log['open_records_count']/cleaning_log['final_cleaned_count']*100:.2f}%)
- **Deduplicated Identifiers**: {cleaning_log['deduplicated_count']}
- **Coordinate Anomalies Flagged**: {cleaning_log['coordinate_anomalies_flagged']}
- **Negative Resolution Durations Flagged**: {cleaning_log['negative_duration_flagged']}

## 2. Statistical Distribution of Resolution Duration
- **Valid Resolution Cases**: {cleaning_log['iqr_statistics'].get('valid_resolution_records', 0):,}
- **Mean Duration**: {cleaning_log['iqr_statistics'].get('mean_hours', 0)} hours
- **Median Duration**: {cleaning_log['iqr_statistics'].get('median_hours', 0)} hours
- **Standard Deviation**: {cleaning_log['iqr_statistics'].get('std_hours', 0)} hours
- **Distribution Skewness**: {cleaning_log['iqr_statistics'].get('skewness', 0)} (Heavy right-tail)
- **Q1 (25th percentile)**: {cleaning_log['iqr_statistics'].get('q1_25th_percentile', 0)} hours
- **Q3 (75th percentile)**: {cleaning_log['iqr_statistics'].get('q3_75th_percentile', 0)} hours
- **IQR (Interquartile Range)**: {cleaning_log['iqr_statistics'].get('iqr', 0)} hours
- **IQR Outlier Upper Threshold**: {cleaning_log['iqr_statistics'].get('upper_bound', 0)} hours
- **Identified Outliers**: {cleaning_log['iqr_statistics'].get('outlier_count', 0)} ({cleaning_log['iqr_statistics'].get('outlier_percentage', 0)}% of valid cases)

## 3. Transformations Applied
""" + "\n".join([f"- {t}" for t in cleaning_log["transformations_applied"]]) + """

## 4. Responsible Interpretation Caveats
1. **Reported Requests vs. Reality**: NYC 311 captures citizen reports, which correlate with civic engagement, digital access, and awareness, not solely underlying physical problem frequency.
2. **Recorded Closure != Citizen Satisfaction**: Closure reflects internal departmental ticket completion status.
3. **Outliers as Operational Prompts**: Extreme resolution durations are flagged for qualitative review, not deleted, as complex municipal interventions legitimately require extensive lead times.
"""

    with open(log_doc_path, "w", encoding="utf-8") as f:
        f.write(cleaning_md)
    with open(log_json_path, "w", encoding="utf-8") as f:
        json.dump(cleaning_log, f, indent=4)
    print(f"[STEP 6] Cleaning log saved to '{log_doc_path}'")

    print("\n==================================================")
    print("DATA PIPELINE COMPLETED SUCCESSFULLY")
    print("==================================================")
    return df_clean


if __name__ == "__main__":
    run_pipeline()
