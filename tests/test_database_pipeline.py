"""
URBAN PULSE: Database Pipeline Verification & Failure Mode Test Suite
Tests both successful database operations and all failure scenarios:
1. Connection success and failure
2. Schema setup and SQL error abort
3. Staging data validation and count mismatch abort
4. End-to-end 4-way pipeline count reconciliation
5. CLI non-zero exit code enforcement on errors
"""

import os
import sys
import subprocess
import mysql.connector

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import (
    get_db_config,
    get_connection,
    test_connection,
    setup_schema,
    validate_staging,
    verify_pipeline_counts,
    query_dataframe,
)


def assert_raises(exc_type, func, *args, **kwargs):
    """Helper to verify exception raising without pytest."""
    try:
        func(*args, **kwargs)
    except exc_type as e:
        return e
    except Exception as e:
        raise AssertionError(f"Expected {exc_type.__name__}, got {type(e).__name__}: {e}")
    raise AssertionError(f"Expected {exc_type.__name__}, but no exception was raised.")


def test_01_successful_connection():
    """Verify that valid database connection succeeds and reports version."""
    success = test_connection()
    assert success is True, "Database connection test should succeed with valid credentials."
    print("[TEST 01 PASS] Database connection test succeeded.")


def test_02_connection_failure_invalid_password():
    """Verify that invalid password raises ConnectionError."""
    orig_pwd = os.environ.get("DB_PASSWORD", None)
    os.environ["DB_PASSWORD"] = "completely_wrong_password_xyz_123"
    try:
        err = assert_raises(ConnectionError, get_connection, with_database=False, max_retries=1)
        assert "Access Denied" in str(err) or "access denied" in str(err).lower()
        print("[TEST 02 PASS] Connection failure with bad password correctly raised ConnectionError.")
    finally:
        if orig_pwd is None:
            os.environ.pop("DB_PASSWORD", None)
        else:
            os.environ["DB_PASSWORD"] = orig_pwd


def test_03_connection_failure_invalid_port():
    """Verify that unreachable port raises ConnectionError after retries."""
    orig_port = os.environ.get("DB_PORT", "3306")
    os.environ["DB_PORT"] = "59999"  # Non-listening port
    try:
        err = assert_raises(ConnectionError, get_connection, with_database=False, max_retries=1, retry_delay=0.1)
        assert "Could not connect" in str(err)
        print("[TEST 03 PASS] Connection failure with offline port correctly raised ConnectionError.")
    finally:
        os.environ["DB_PORT"] = orig_port


def test_04_schema_setup_nonexistent_file():
    """Verify that a non-existent schema file raises FileNotFoundError."""
    assert_raises(FileNotFoundError, setup_schema, "sql/non_existent_schema_12345.sql")
    print("[TEST 04 PASS] Missing schema file correctly raised FileNotFoundError.")


def test_05_schema_setup_syntax_error():
    """Verify that malformed SQL statements raise RuntimeError and stop execution."""
    bad_schema_path = "tests/bad_schema_temp.sql"
    with open(bad_schema_path, "w", encoding="utf-8") as f:
        f.write("CREATE INVALID_SQL_SYNTAX TABLE broken_table;")

    try:
        err = assert_raises(RuntimeError, setup_schema, bad_schema_path)
        assert "failed on statement" in str(err)
        print("[TEST 05 PASS] SQL syntax error correctly raised RuntimeError.")
    finally:
        if os.path.exists(bad_schema_path):
            os.remove(bad_schema_path)


def test_06_staging_validation_success():
    """Verify that staging table with 100,000 records passes validation."""
    is_valid, results = validate_staging(expected_count=100000)
    assert is_valid is True
    assert results["staged_count"] == 100000
    assert results["distinct_keys"] == 100000
    assert results["null_keys"] == 0
    assert results["null_created"] == 0
    assert results["count_match"] is True
    print("[TEST 06 PASS] Staging validation passed 100% with exact 100,000 rows.")


def test_07_staging_validation_mismatch_failure():
    """Verify that an expected count mismatch raises ValueError and stops pipeline."""
    err = assert_raises(ValueError, validate_staging, expected_count=99999)  # 1 record mismatch
    assert "Count mismatch" in str(err)
    print("[TEST 07 PASS] Staging count mismatch correctly raised ValueError.")


def test_08_pipeline_reconciliation_success():
    """Verify strict 4-way row-count reconciliation across raw, cleaned, staging, and production."""
    counts = verify_pipeline_counts()
    assert counts["raw_csv_count"] == 100000
    assert counts["cleaned_csv_count"] == 100000
    assert counts["staging_db_count"] == 100000
    assert counts["production_db_count"] == 100000
    assert counts["db_connected"] is True
    assert counts["reconciliation_passed"] is True
    print("[TEST 08 PASS] 4-way pipeline row counts perfectly reconciled at 100,000 records.")


def test_09_pipeline_reconciliation_missing_file_failure():
    """Verify that missing CSV files raise FileNotFoundError during reconciliation."""
    assert_raises(FileNotFoundError, verify_pipeline_counts, raw_path="data/missing_raw_file.csv")
    print("[TEST 09 PASS] Missing raw dataset correctly raised FileNotFoundError.")


def test_10_query_dataframe():
    """Verify that query_dataframe executes against service_requests and returns DataFrame."""
    df = query_dataframe("SELECT COUNT(*) AS total_count FROM service_requests;")
    assert len(df) == 1
    assert int(df.iloc[0]["total_count"]) == 100000
    print("[TEST 10 PASS] query_dataframe verified 100,000 records in production table.")


def test_11_cli_test_exit_code_success():
    """Verify that 'python src/database.py --test' exits with code 0."""
    res = subprocess.run([sys.executable, "src/database.py", "--test"], capture_output=True, text=True)
    assert res.returncode == 0, f"Expected 0, got {res.returncode}: {res.stderr}"
    assert "[SUCCESS] Connected to MySQL" in res.stdout
    print("[TEST 11 PASS] CLI --test exited with code 0.")


def test_12_cli_verify_exit_code_success():
    """Verify that 'python src/database.py --verify' exits with code 0."""
    res = subprocess.run([sys.executable, "src/database.py", "--verify"], capture_output=True, text=True)
    assert res.returncode == 0, f"Expected 0, got {res.returncode}: {res.stderr}"
    assert "All pipeline counts reconciled 100%" in res.stdout
    print("[TEST 12 PASS] CLI --verify exited with code 0.")


def test_13_cli_exit_code_failure_on_bad_credentials():
    """Verify that CLI exits with non-zero exit code (1) when database connection fails."""
    env = os.environ.copy()
    env["DB_PASSWORD"] = "deliberately_wrong_password_999"
    res = subprocess.run([sys.executable, "src/database.py", "--test"], env=env, capture_output=True, text=True)
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output: {res.stdout} {res.stderr}"
    assert "[ABORT]" in res.stdout or "failed" in res.stdout
    print("[TEST 13 PASS] CLI test with bad credentials correctly aborted with exit code 1.")


def test_14_cli_verify_exit_code_failure_on_csv_mismatch():
    """Verify that CLI --verify exits with code 1 if cleaned CSV is missing or mismatched."""
    res = subprocess.run([sys.executable, "src/database.py", "--verify", "--csv", "data/non_existent.csv"], capture_output=True, text=True)
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}."
    assert "[ABORT]" in res.stdout
    print("[TEST 14 PASS] CLI verify with missing CSV correctly aborted with exit code 1.")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING URBAN PULSE DATABASE INTEGRATION TEST SUITE")
    print("==================================================")
    test_funcs = [
        test_01_successful_connection,
        test_02_connection_failure_invalid_password,
        test_03_connection_failure_invalid_port,
        test_04_schema_setup_nonexistent_file,
        test_05_schema_setup_syntax_error,
        test_06_staging_validation_success,
        test_07_staging_validation_mismatch_failure,
        test_08_pipeline_reconciliation_success,
        test_09_pipeline_reconciliation_missing_file_failure,
        test_10_query_dataframe,
        test_11_cli_test_exit_code_success,
        test_12_cli_verify_exit_code_success,
        test_13_cli_exit_code_failure_on_bad_credentials,
        test_14_cli_verify_exit_code_failure_on_csv_mismatch,
    ]
    passed = 0
    for tf in test_funcs:
        try:
            tf()
            passed += 1
        except Exception as e:
            print(f"[TEST FAIL] {tf.__name__}: {e}")
            raise
    print("==================================================")
    print(f"ALL {passed}/{len(test_funcs)} DATABASE TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================")

