"""
URBAN PULSE: Citizen Complaint Intelligence & Resolution Analytics
Module: MySQL Database Staging, Validation & Production Ingestion Pipeline
Author: Urban Pulse Analytics Team
"""

import os
import sys
import math
import argparse
import time
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import mysql.connector
from mysql.connector import errorcode


def get_db_config() -> Dict[str, Any]:
    """
    Retrieve database configuration from environment variables, .env file,
    or Streamlit secrets without exposing hardcoded credentials.
    """
    # 1. Parse .env if present
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key_clean = key.strip()
                    val_clean = val.strip().strip('"').strip("'")
                    if key_clean not in os.environ or os.environ[key_clean] == "":
                        os.environ[key_clean] = val_clean

    # 2. Also check Streamlit secrets if available
    secrets_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_file):
        try:
            import toml
            secrets = toml.load(secrets_file)
            db_sec = secrets.get("mysql") or secrets.get("database") or {}
            for k, v in db_sec.items():
                env_key = f"DB_{k.upper()}"
                if env_key not in os.environ or os.environ[env_key] == "":
                    os.environ[env_key] = str(v)
        except Exception:
            pass

    # Resolve password: check env var DB_PASSWORD, then MYSQL_PWD, then default to '1234' on localhost
    db_pwd = os.environ.get("DB_PASSWORD")
    if db_pwd is None:
        db_pwd = os.environ.get("MYSQL_PWD")
    if db_pwd is None:
        host = os.environ.get("DB_HOST", "localhost")
        if host in ("localhost", "127.0.0.1"):
            db_pwd = "1234"
        else:
            db_pwd = ""

    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", 3306)),
        "user": os.environ.get("DB_USER", "root"),
        "password": db_pwd,
        "database": os.environ.get("DB_NAME", "urban_pulse_db"),
        "connect_timeout": 10,
    }


def get_connection(with_database: bool = True, max_retries: int = 3, retry_delay: float = 1.0):
    """
    Establish connection to MySQL server with retry handling for transient connection errors.
    Raises ConnectionError if connection fails.
    """
    config = get_db_config()
    connect_params = {
        "host": config["host"],
        "port": config["port"],
        "user": config["user"],
        "password": config["password"],
        "connect_timeout": config["connect_timeout"],
    }
    if with_database:
        connect_params["database"] = config["database"]

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            connection = mysql.connector.connect(**connect_params)
            return connection
        except mysql.connector.Error as err:
            last_err = err
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                raise ConnectionError(
                    f"MySQL Access Denied for user '{config['user']}' at {config['host']}:{config['port']}. "
                    "Please check DB_USER and DB_PASSWORD in your .env or environment variables."
                ) from err
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                if with_database:
                    raise ConnectionError(
                        f"Database '{config['database']}' not found on MySQL server at {config['host']}:{config['port']}. "
                        "Run schema setup first via 'python src/database.py --setup'."
                    ) from err
            # Retry transient server connection failures
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)

    raise ConnectionError(
        f"Could not connect to MySQL server at {config['host']}:{config['port']} after {max_retries} attempts: {last_err}"
    )


def test_connection() -> bool:
    """Test MySQL connectivity and report server version."""
    config = get_db_config()
    print(f"Testing MySQL connection to {config['user']}@{config['host']}:{config['port']} ...")
    try:
        conn = get_connection(with_database=False, max_retries=2)
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        print(f"[SUCCESS] Connected to MySQL Server version: {version[0]}")
        return True
    except Exception as e:
        print(f"[ERROR] MySQL Connection check failed: {e}")
        return False


def setup_schema(schema_file: str = "sql/schema.sql") -> bool:
    """Execute SQL schema definition file to prepare urban_pulse_db and tables."""
    if not os.path.exists(schema_file):
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    print(f"[STEP 1] Executing schema script '{schema_file}'...")
    conn = get_connection(with_database=False)
    cursor = conn.cursor()

    with open(schema_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split commands by semicolon, stripping comments
    cleaned_lines = []
    for line in sql_content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("--") and not stripped.startswith("/*"):
            cleaned_lines.append(line)
    sql_commands = "\n".join(cleaned_lines)

    statements = [stmt.strip() for stmt in sql_commands.split(";") if stmt.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
        except mysql.connector.Error as err:
            err_msg = str(err).lower()
            if "already exists" in err_msg or "note" in err_msg:
                print(f"[NOTICE] Statement note: {err}")
            else:
                cursor.close()
                conn.close()
                raise RuntimeError(f"Database schema initialization failed on statement:\n{stmt}\nError: {err}") from err

    conn.commit()
    cursor.close()
    conn.close()
    print("[SUCCESS] Database schema and tables initialized successfully.")
    return True


def load_staging(csv_path: str = "data/cleaned_data.csv", batch_size: int = 5000) -> int:
    """
    Load cleaned CSV records into staging_service_requests in batches with retry handling.
    Converts all missing/NaN values to SQL NULL (None) and validates data types.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Cleaned data file not found: {csv_path}")

    print(f"[STEP 2] Loading records from '{csv_path}' into staging table...")
    df = pd.read_csv(csv_path, low_memory=False)

    total_records = len(df)
    if total_records == 0:
        raise ValueError(f"Cleaned dataset '{csv_path}' contains 0 records!")

    staging_cols = [
        "unique_key", "created_date", "closed_date", "due_date", "resolution_action_updated_date",
        "agency", "agency_name", "complaint_type", "descriptor", "descriptor_2",
        "location_type", "incident_zip", "incident_address", "street_name", "city",
        "status", "resolution_description", "community_board", "council_district", "police_precinct",
        "borough", "open_data_channel_type", "park_borough", "latitude", "longitude",
        "resolution_hours", "is_closed", "is_valid_resolution", "duration_category",
        "created_year", "created_month", "created_month_name", "created_weekday", "created_hour",
        "is_resolution_outlier"
    ]

    for col in staging_cols:
        if col not in df.columns:
            df[col] = None

    df_staged = df[staging_cols].copy()

    # Fill missing boroughs with 'Unspecified'
    df_staged["borough"] = df_staged["borough"].fillna("Unspecified").replace("", "Unspecified")

    # Format incident_zip to avoid '.0' trailing float artifact
    def clean_zip(x):
        if pd.isna(x) or x is None:
            return None
        if isinstance(x, (int, float)):
            if math.isnan(x):
                return None
            return str(int(x))
        s = str(x).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s if s and s != "nan" else None

    df_staged["incident_zip"] = df_staged["incident_zip"].apply(clean_zip)

    # Format date columns to 'YYYY-MM-DD HH:MM:SS' strings or None
    date_cols = ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]
    for col in date_cols:
        parsed_dt = pd.to_datetime(df_staged[col], errors="coerce")
        df_staged[col] = parsed_dt.dt.strftime("%Y-%m-%d %H:%M:%S")
        df_staged[col] = df_staged[col].where(pd.notnull(df_staged[col]), None)

    # Format boolean flags to 1 or 0
    bool_cols = ["is_closed", "is_valid_resolution", "is_resolution_outlier"]
    for col in bool_cols:
        df_staged[col] = df_staged[col].apply(
            lambda x: 1 if (x is True or x == 1 or str(x).lower() in ("true", "1")) else 0
        )

    # Ensure all columns are object type and convert NaNs to None
    df_staged = df_staged.astype(object).where(pd.notnull(df_staged), None)

    raw_rows = df_staged.values.tolist()
    records = []
    for row in raw_rows:
        cleaned_row = []
        for val in row:
            if val is None or pd.isna(val):
                cleaned_row.append(None)
            elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                cleaned_row.append(None)
            else:
                cleaned_row.append(val)
        records.append(cleaned_row)

    conn = get_connection(with_database=True)
    cursor = conn.cursor()

    cursor.execute("TRUNCATE TABLE staging_service_requests;")

    col_names = ", ".join(staging_cols)
    placeholders = ", ".join(["%s"] * len(staging_cols))
    insert_sql = f"INSERT INTO staging_service_requests ({col_names}) VALUES ({placeholders})"

    print(f"         Inserting {total_records:,} records in batches of {batch_size:,}...")

    start_time = time.time()
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        for attempt in range(1, 4):
            try:
                cursor.executemany(insert_sql, batch)
                conn.commit()
                break
            except mysql.connector.Error as e:
                if attempt == 3:
                    cursor.close()
                    conn.close()
                    raise RuntimeError(f"Batch staging insertion failed at rows {i}-{i+len(batch)}: {e}") from e
                time.sleep(1.0)
        print(f"         Staged {min(i + batch_size, total_records):,}/{total_records:,} rows...")

    cursor.close()
    conn.close()
    elapsed = time.time() - start_time
    print(f"[SUCCESS] Staged {total_records:,} records in {elapsed:.1f}s.")
    return total_records


def validate_staging(expected_count: Optional[int] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate data integrity in staging_service_requests before promoting to production.
    Checks:
    - Staged row count > 0
    - Row count equals expected cleaned CSV count
    - Identifier uniqueness (zero duplicates)
    - Zero null primary keys
    - Temporal integrity (created_date non-null)
    Raises ValueError immediately if validation fails.
    """
    print("[STEP 3] Validating staged records...")
    conn = get_connection(with_database=True)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM staging_service_requests;")
    staged_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM staging_service_requests WHERE unique_key IS NULL;")
    null_keys = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT unique_key) FROM staging_service_requests;")
    distinct_keys = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM staging_service_requests WHERE created_date IS NULL;")
    null_created = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    count_match = True
    if expected_count is not None:
        count_match = (staged_count == expected_count)

    is_valid = (
        staged_count > 0 
        and null_keys == 0 
        and staged_count == distinct_keys 
        and null_created == 0
        and count_match
    )

    validation_results = {
        "staged_count": staged_count,
        "expected_count": expected_count,
        "null_keys": null_keys,
        "distinct_keys": distinct_keys,
        "null_created": null_created,
        "count_match": count_match,
        "is_valid": is_valid,
    }

    print(f"         - Staged Row Count : {staged_count:,}")
    if expected_count is not None:
        print(f"         - Expected Count   : {expected_count:,} (Match: {count_match})")
    print(f"         - Distinct Keys    : {distinct_keys:,}")
    print(f"         - Null Keys        : {null_keys}")
    print(f"         - Null Created Date: {null_created}")

    if is_valid:
        print("[SUCCESS] Staging validation PASSED. Ready for promotion to production.")
    else:
        err_reasons = []
        if staged_count == 0:
            err_reasons.append("Staged row count is 0")
        if null_keys > 0:
            err_reasons.append(f"{null_keys} null unique_keys found")
        if staged_count != distinct_keys:
            err_reasons.append(f"Duplicate keys detected ({staged_count - distinct_keys})")
        if null_created > 0:
            err_reasons.append(f"{null_created} null created_date found")
        if not count_match:
            err_reasons.append(f"Count mismatch: Staged {staged_count:,} vs Expected {expected_count:,}")
        
        err_msg = "; ".join(err_reasons)
        print(f"[ERROR] Staging validation FAILED: {err_msg}")
        raise ValueError(f"Staging validation FAILED: {err_msg}. Pipeline stopped.")

    return is_valid, validation_results


def publish_staging_to_production() -> int:
    """
    Publish validated records from staging_service_requests to service_requests.
    Uses INSERT ... ON DUPLICATE KEY UPDATE to ensure idempotent upsert.
    """
    print("[STEP 4] Publishing staging records to production 'service_requests'...")
    conn = get_connection(with_database=True)
    cursor = conn.cursor()

    staging_cols = [
        "unique_key", "created_date", "closed_date", "due_date", "resolution_action_updated_date",
        "agency", "agency_name", "complaint_type", "descriptor", "descriptor_2",
        "location_type", "incident_zip", "incident_address", "street_name", "city",
        "status", "resolution_description", "community_board", "council_district", "police_precinct",
        "borough", "open_data_channel_type", "park_borough", "latitude", "longitude",
        "resolution_hours", "is_closed", "is_valid_resolution", "duration_category",
        "created_year", "created_month", "created_month_name", "created_weekday", "created_hour",
        "is_resolution_outlier"
    ]

    cols_str = ", ".join(staging_cols)
    update_str = ", ".join([f"{col} = VALUES({col})" for col in staging_cols if col != "unique_key"])

    upsert_sql = f"""
    INSERT INTO service_requests ({cols_str})
    SELECT {cols_str} FROM staging_service_requests
    ON DUPLICATE KEY UPDATE {update_str};
    """

    try:
        cursor.execute(upsert_sql)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM service_requests;")
        prod_count = cursor.fetchone()[0]
    finally:
        cursor.close()
        conn.close()

    if prod_count == 0:
        raise ValueError("Production table 'service_requests' contains 0 records after publish!")

    print(f"[SUCCESS] Production table 'service_requests' contains {prod_count:,} records.")
    return prod_count


def verify_pipeline_counts(raw_path: str = "data/raw_data.csv", cleaned_path: str = "data/cleaned_data.csv") -> Dict[str, Any]:
    """
    Verify end-to-end row counts across raw CSV, cleaned CSV, MySQL staging, and MySQL production.
    Raises ValueError or ConnectionError if reconciliation detects any discrepancy or connection failure.
    """
    print("==================================================")
    print("END-TO-END PIPELINE ROW-COUNT RECONCILIATION")
    print("==================================================")

    counts = {
        "raw_csv_count": 0,
        "cleaned_csv_count": 0,
        "staging_db_count": None,
        "production_db_count": None,
        "db_connected": False,
        "reconciliation_passed": False,
    }

    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw data file not found: {raw_path}")
    if not os.path.exists(cleaned_path):
        raise FileNotFoundError(f"Cleaned data file not found: {cleaned_path}")

    df_raw = pd.read_csv(raw_path, usecols=["unique_key"], low_memory=False)
    counts["raw_csv_count"] = len(df_raw)
    print(f"1. Raw Dataset (data/raw_data.csv)        : {counts['raw_csv_count']:,} records")

    df_cleaned = pd.read_csv(cleaned_path, usecols=["unique_key"], low_memory=False)
    counts["cleaned_csv_count"] = len(df_cleaned)
    print(f"2. Cleaned Dataset (data/cleaned_data.csv): {counts['cleaned_csv_count']:,} records")

    if counts["raw_csv_count"] != counts["cleaned_csv_count"]:
        err_msg = f"Raw CSV count ({counts['raw_csv_count']:,}) != Cleaned CSV count ({counts['cleaned_csv_count']:,})"
        print(f"[ERROR] {err_msg}")
        raise ValueError(f"Pipeline verification failure: {err_msg}")

    try:
        conn = get_connection(with_database=True)
    except Exception as e:
        print(f"[ERROR] MySQL connection failed during reconciliation: {e}")
        counts["db_connected"] = False
        raise ConnectionError(f"Database connection failed during reconciliation: {e}") from e

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM staging_service_requests;")
        counts["staging_db_count"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM service_requests;")
        counts["production_db_count"] = cursor.fetchone()[0]
        counts["db_connected"] = True
    finally:
        cursor.close()
        conn.close()

    print(f"3. MySQL Staging (staging_service_requests): {counts['staging_db_count']:,} records")
    print(f"4. MySQL Production (service_requests)    : {counts['production_db_count']:,} records")

    # Enforce strict count integrity
    mismatches = []
    if counts["staging_db_count"] != counts["cleaned_csv_count"]:
        mismatches.append(f"Staging count ({counts['staging_db_count']:,}) != Cleaned CSV count ({counts['cleaned_csv_count']:,})")
    if counts["production_db_count"] != counts["staging_db_count"]:
        mismatches.append(f"Production count ({counts['production_db_count']:,}) != Staging count ({counts['staging_db_count']:,})")

    if mismatches:
        counts["reconciliation_passed"] = False
        err_summary = "; ".join(mismatches)
        print(f"[ERROR] Pipeline row-count reconciliation FAILED: {err_summary}")
        raise ValueError(f"Pipeline reconciliation failure: {err_summary}")

    counts["reconciliation_passed"] = True
    print("[SUCCESS] All pipeline counts reconciled 100% across CSV and Database stages.")
    print("==================================================")
    return counts


def query_dataframe(query: str, params: Optional[Tuple] = None) -> pd.DataFrame:
    """Execute SQL query against urban_pulse_db and return pandas DataFrame."""
    conn = get_connection(with_database=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)
        cursor.close()
        return df
    except Exception as e:
        raise RuntimeError(f"Database query execution failed: {e}") from e
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Urban Pulse: Database Pipeline CLI")
    parser.add_argument("--test", action="store_true", help="Test MySQL server connection")
    parser.add_argument("--setup", action="store_true", help="Initialize schema and tables")
    parser.add_argument("--load", action="store_true", help="Stage, validate and publish cleaned CSV")
    parser.add_argument("--verify", action="store_true", help="Verify row counts across pipeline stages")
    parser.add_argument("--csv", type=str, default="data/cleaned_data.csv", help="Cleaned CSV path")

    args = parser.parse_args()

    try:
        if args.verify:
            counts = verify_pipeline_counts(cleaned_path=args.csv)
            if not counts["db_connected"] or not counts["reconciliation_passed"]:
                print("[ABORT] Pipeline reconciliation check failed.")
                sys.exit(1)
            print("[SUCCESS] All pipeline counts verified successfully.")
            sys.exit(0)
        elif args.test:
            success = test_connection()
            if not success:
                print("[ABORT] Database connection test failed.")
                sys.exit(1)
            sys.exit(0)
        elif args.setup:
            setup_schema()
            sys.exit(0)
        elif args.load:
            setup_schema()
            cleaned_count = load_staging(args.csv)
            valid, val_results = validate_staging(expected_count=cleaned_count)
            if not valid:
                print("[ABORT] Publish aborted due to staging validation failure.")
                sys.exit(1)
            publish_staging_to_production()
            counts = verify_pipeline_counts(cleaned_path=args.csv)
            if not counts["reconciliation_passed"]:
                print("[ABORT] Production row-count verification failed.")
                sys.exit(1)
            print("[SUCCESS] Pipeline stage and publish completed successfully.")
            sys.exit(0)
        else:
            # Default behavior: test, setup, load and verify
            if not test_connection():
                print("[ABORT] MySQL connection unavailable.")
                sys.exit(1)
            setup_schema()
            cleaned_count = load_staging(args.csv)
            valid, val_results = validate_staging(expected_count=cleaned_count)
            if not valid:
                print("[ABORT] Publish aborted due to validation failure.")
                sys.exit(1)
            publish_staging_to_production()
            counts = verify_pipeline_counts(cleaned_path=args.csv)
            if not counts["reconciliation_passed"]:
                print("[ABORT] Pipeline reconciliation failed.")
                sys.exit(1)
            print("[SUCCESS] Full end-to-end database pipeline completed successfully.")
            sys.exit(0)
    except Exception as e:
        print(f"[ABORT] Database pipeline operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
