"""
Urban Pulse: Automated End-to-End Pipeline Runner
Executes the core data engineering automation stages in strict order:
1. Data Extraction (src/extraction.py)
2. Data Cleaning & Feature Engineering (src/cleaning.py)
3. MySQL Database Setup & Batch Ingestion (src/database.py --load)

Enforces strict failure-handling logic:
If any stage fails, the pipeline halts immediately with a non-zero exit code
and never displays PIPELINE COMPLETE.
"""

import sys
import argparse
import subprocess


def run_stage(cmd_list, desc):
    """
    Execute a pipeline stage command.
    If the stage fails (returncode != 0), halts immediately with that exit code.
    """
    print(f"\n==================================================")
    print(f"[PIPELINE STAGE] {desc}")
    print(f"Command: {' '.join(cmd_list)}")
    print(f"==================================================")

    res = subprocess.run(cmd_list)
    if res.returncode != 0:
        print(f"\n==================================================")
        print(f"[PIPELINE ABORTED] Stage '{desc}' failed with exit code {res.returncode}.")
        print("Stopping pipeline immediately. Subsequent stages will not run.")
        print("==================================================")
        sys.exit(res.returncode)

    print(f"[SUCCESS] Stage '{desc}' completed successfully.")
    return res.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Urban Pulse: Automated End-to-End Pipeline Runner (Extraction -> Cleaning -> Database)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Target record extraction limit (default: uses extraction.py default)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="NYC Open Data Socrata App Token",
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction stage if raw data is already present",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force fresh extraction in extraction stage",
    )
    args = parser.parse_args()

    py = sys.executable

    # ----------------------------------------------------
    # Stage 1: Data Extraction
    # ----------------------------------------------------
    if not args.skip_extraction:
        extract_cmd = [py, "src/extraction.py"]
        if args.limit:
            extract_cmd.extend(["--limit", str(args.limit)])
        if args.token:
            extract_cmd.extend(["--token", args.token])
        if args.force:
            extract_cmd.append("--force")
        run_stage(extract_cmd, "Stage 1: Data Extraction (NYC Open Data API)")
    else:
        print("\n[INFO] Skipping Stage 1 (Data Extraction) as requested.")

    # ----------------------------------------------------
    # Stage 2: Data Cleaning & Feature Engineering
    # ----------------------------------------------------
    clean_cmd = [py, "src/cleaning.py"]
    run_stage(clean_cmd, "Stage 2: Data Cleaning & Feature Engineering")

    # ----------------------------------------------------
    # Stage 3: Database Setup & Batch Ingestion
    # ----------------------------------------------------
    db_cmd = [py, "src/database.py", "--load"]
    run_stage(db_cmd, "Stage 3: MySQL Database Setup & Batch Staging Load")

    # ----------------------------------------------------
    # All stages succeeded
    # ----------------------------------------------------
    print("\n==================================================")
    print("[PIPELINE COMPLETE] All stages (Extraction, Cleaning, Database) executed successfully.")
    print("Dataset is ready for Streamlit dashboard execution.")
    print("Run: streamlit run app/dashboard.py")
    print("==================================================")


if __name__ == "__main__":
    main()
