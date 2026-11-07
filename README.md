# 🏙️ URBAN PULSE: Citizen Complaint Intelligence & Resolution Analytics

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end data analytics and civic intelligence pipeline built on **100,000 genuine records from the NYC 311 Open Data API (spanning 2020-01-01 to 2026-11-02)**. Urban Pulse extracts, cleans, validates, models, and visualizes civic complaint records to deliver actionable operational insights into municipal agency workload, turnaround velocity, geographic concentration, and civic service bottlenecks.

---

## 📌 Table of Contents
1. [Project Overview & Problem Statement](#-project-overview--problem-statement)
2. [Key Skills & Takeaways](#-key-skills--takeaways)
3. [Architecture & Workflow](#-architecture--workflow)
4. [Dataset & Selected Schema Fields](#-dataset--selected-schema-fields)
5. [Data Cleaning, Quality Validation & Feature Engineering](#-data-cleaning-quality-validation--feature-engineering)
6. [Statistical Checking: Spread, Skewness & Outliers](#-statistical-checking-spread-skewness--outliers)
7. [MySQL Database Architecture](#-mysql-database-architecture)
8. [The 15 Core Analyst Investigations](#-the-15-core-analyst-investigations)
9. [Five Dashboard KPIs](#-five-dashboard-kpis)
10. [Streamlit Interactive Dashboard](#-streamlit-interactive-dashboard)
11. [Installation & Execution Guide](#-installation--execution-guide)
12. [Project Structure](#-project-structure)
13. [Limitations & Responsible Interpretation](#-limitations--responsible-interpretation)

---

## 🏙️ Project Overview & Problem Statement
Municipal service departments receive massive volumes of citizen requests via 311 hotlines, web portals, and mobile apps. These records reveal critical patterns in urban infrastructure health, departmental demand peaks, spatial complaint clusters, and agency turnaround performance. 

Raw 311 service request data is high-volume, inconsistent, incomplete, and heavily right-skewed by complex long-running municipal cases. 

**URBAN PULSE** designs and deploys an enterprise-grade analytics pipeline that:
- Ingests **100,000 live genuine service requests** from the **NYC Open Data Socrata (SODA) API**.
- Cleans, standardizes, and enriches records with temporal features and non-parametric resolution metrics.
- Stores validated records in a **MySQL** warehouse with resilient staging and production schemas.
- Answers **15 core civic analyst investigations** via optimized SQL queries and Python EDA.
- Publishes an interactive **Streamlit** dashboard featuring 5 executive KPIs, geospatial maps, and filterable investigation views.

---

## 🐍 Key Skills & Takeaways
- **Python for Data Analytics:** Clean, transform, and evaluate real-world civic records with `pandas` and `numpy`.
- **Resilient API Extraction:** Retrieve paginated data from NYC Open Data (`erm2-nwe9.json`) with backoff retries, rate limit handling, dynamic keyset cursor pagination, and raw snapshot preservation.
- **Statistics & EDA:** Analyze right-skewed distributions, Tukey IQR outlier screening, and non-parametric central tendency (mean vs. median).
- **SQL & MySQL Warehousing:** Staging tables, automated validation gates, indexed analytical production schemas, and window functions.
- **Streamlit & Data Storytelling:** Build interactive, multi-page analytical dashboards with Plotly and dual-mode data loading (MySQL + offline CSV fallback).

---

## 🔄 Architecture & Workflow

```mermaid
flowchart LR
    A["NYC Open Data 311 API"] -->|SODA REST API| B["src/extraction.py"]
    B -->|Raw CSV Snapshot (100,000 rows)| C["data/raw_data.csv"]
    C -->|Quality Validation & Feature Engineering| D["src/cleaning.py"]
    D -->|Cleaned Dataset (100,000 rows)| E["data/cleaned_data.csv"]
    D -->|IQR Outlier Records (16,636 rows)| F["data/resolution_outliers.csv"]
    D -->|Schema Documentation| G["docs/data_dictionary.md"]
    E -->|Staging Batch Ingestion| H["staging_service_requests (MySQL)"]
    H -->|Validation Gate| I["service_requests (Production MySQL)"]
    I -->|15 Core SQL Queries| J["sql/analysis_queries.sql"]
    I -->|Interactive Multi-Page BI| K["app/dashboard.py (Streamlit)"]
    E -.->|Resilient Offline Fallback| K
```

---

## 📊 Dataset & Selected Schema Fields
The pipeline extracts directly from the official NYC 311 dataset endpoint (`https://data.cityofnewyork.us/resource/erm2-nwe9.json`). The extraction pipeline retrieves the **18 populated source fields** from the live API endpoint (with candidate/full-schema fields documented in the data dictionary):

| Category | Fields Retained |
| :--- | :--- |
| **Identifiers & Timestamps** | `unique_key`, `created_date`, `closed_date`, `due_date`, `resolution_action_updated_date` |
| **Agency & Classification** | `agency`, `agency_name`, `complaint_type`, `descriptor`, `location_type` |
| **Geographic Location** | `incident_zip`, `incident_address`, `street_name`, `city`, `borough`, `latitude`, `longitude` |
| **Operational Status** | `status` |

---

## 🧹 Data Cleaning, Quality Validation & Feature Engineering
Executed via `src/cleaning.py`:
1. **Deduplication:** Primary key `unique_key` integrity verified; zero duplicate keys permitted (100,000 unique keys).
2. **Temporal Parsing & Normalization:** Converted timestamps to America/New_York local time (`created_date`, `closed_date`, `due_date`).
3. **Text Standardization:** Whitespace stripped, missing values tagged as `"Unknown"`, and borough names standardized across five boroughs.
4. **Coordinate Bounding Box Check:** Verified latitude $[40.40, 41.10]$ and longitude $[-74.35, -73.65]$; out-of-bounds spatial anomalies flagged.
5. **Feature Engineering:**
   - `resolution_hours`: Elapsed time in hours $(closed\_date - created\_date)$.
   - `is_closed`: Boolean indicator for completed tickets (`closed_date.notna()`).
   - `is_valid_resolution`: Flag ensuring non-negative durations $(resolution\_hours \ge 0)$; 137 negative duration anomalies detected and nulled.
   - `created_year`, `created_month`, `created_month_name`, `created_weekday`, `created_hour`.
   - `duration_category`: Operational tiers (`< 24h`, `24-72h`, `> 72h`, `Unresolved`).

---

## 📈 Statistical Checking: Spread, Skewness & Outliers
Civic resolution durations exhibit heavy right-tailed skewness (+10.12). Arithmetic means are severely distorted by complex long-running municipal cases.
- **Evaluated Valid Cases:** 98,255 records
- **Mean Duration:** 379.42 hours (~15.8 days)
- **Median Duration:** **2.92 hours** (~0.12 days)
- **Spread:** $Q1 = 0.63$ hours, $Q3 = 56.80$ hours, $\text{IQR} = 56.16$ hours
- **Outlier Screening:** Upper cutoff $= Q3 + 1.5 \times \text{IQR} = \mathbf{141.04\text{ hours}}$ (~5.9 days).
- **Outlier Count:** 16,636 cases (16.93% of valid closed tickets).
- **Outlier Handling:** Flagged in `data/resolution_outliers.csv` as **investigation prompts**, not deleted, since lengthy civic cases reflect complex physical or legal intervention.

---

## 🗄️ MySQL Database Architecture
Database configuration is loaded securely from environment variables (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).

### Workflow:
1. `sql/schema.sql`: Prepares `urban_pulse_db`, `staging_service_requests`, and indexed `service_requests`.
2. `src/database.py`:
   - Truncates and batch-inserts records into `staging_service_requests`.
   - Runs validation gates (row count equality, non-null `unique_key`, zero duplicates, date validity).
   - Promotes validated records to `service_requests` via idempotent upsert (`INSERT ... ON DUPLICATE KEY UPDATE`).
   - Verifies end-to-end counts from raw CSV to cleaned CSV to staging to production.

---

## 🔍 The 15 Core Analyst Investigations
Documented in detail in `docs/analyst_investigations.md` and runnable via `sql/analysis_queries.sql`:

1. **Total Distinct Request Volume:** Verified $N=100,000$ distinct requests across 18 municipal agencies (2020-01-01 00:00:00 to 2026-11-02 23:59:46).
2. **Top 10 Complaint Categories:** `Noise - Residential` (18.32%) and `Illegal Parking` (13.31%) dominate public demand.
3. **Agency Workload Distribution:** NYPD (55.60%) and HPD (16.85%) handle over 72% of all inbound complaints.
4. **Request Volume by Borough:** Brooklyn (29.94%) and Queens (23.44%) lead volume due to residential scale.
5. **Monthly Request Trend:** Evaluated across 83 historical months showing winter heating surges vs. summer noise spikes.
6. **Demand by Weekday and Hour:** Intake volume peaks on Friday (16,944 requests) and late night / midnight hours (hour 0 with 17,135 requests).
7. **Status Distribution:** 98.39% of tickets recorded as `Closed` with valid completion timestamp (98,392 closed; 1,608 active/pending).
8. **Descriptive Statistics for Resolution:** Severe mean-to-median divergence (379.42h mean vs. 2.92h median; std 2,018.25h).
9. **Median Resolution by Complaint Category:** Urgent noise and parking resolve in <3 hours; complex building/housing cases require extended lead times.
10. **Median Resolution by Agency:** NYPD (0.87h) vs. DOT (48.25h), DSNY (50.94h), and HPD (97.14h).
11. **IQR-Based Outlier Investigation:** 16,636 cases (16.93%) identified above the 141.04-hour cutoff ($Q1=0.63\text{h}, Q3=56.80\text{h}, \text{IQR}=56.16\text{h}$).
12. **Skewness & Distribution Bins:** Distribution skewness of +10.124; 22.37% span over 72 hours.
13. **Geographic Complaint Concentration:** Spatial concentration across top zip codes per borough (e.g., Bronx 10466, Brooklyn 11226, Queens 11385).
14. **Recorded Closure-Rate Comparison:** Near-complete recorded closure rates led by emergency response agencies (98.39% citywide baseline).
15. **High-Volume & Long-Resolution Bottlenecks:** 42 critical operational bottlenecks identified exceeding median demand cutoff (47) and median duration (73.12 hours).

---

## 🎯 Five Dashboard KPIs
Prominently featured as 5 separate cards on the Streamlit dashboard:

1. **Total Requests:** Total distinct request identifiers in the active filter selection (100,000 citywide baseline).
2. **Recorded Closure Rate (%):** Share of filtered rows with recorded closure date (98.39% baseline, 98,392 closed).
3. **Pending Resolution:** Current balance of pending or in-progress tickets (1,608 cases, 1.61%).
4. **Median Resolution (Hours):** Non-parametric central turnaround time for valid closed cases (2.92 hours baseline).
5. **Over-72-Hour Resolution Rate (%):** Proportion of valid closed tickets requiring extended lead times (22.37% baseline).

---

## 🚀 Installation & Execution Guide

### 1. Clone & Set Up Environment
```bash
# Navigate to project folder
cd Urban_pulse_guvi_project

# Activate existing virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows Command Prompt:
.\venv\Scripts\activate.bat

# Install dependencies (if needed)
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional for MySQL)
Copy `.env.example` to `.env` in the project root:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=urban_pulse_db
```

### 3. Run Pipeline Scripts
```bash
# Step A: Data Extraction (Genuine NYC 311 Socrata Open Data API)
python src/extraction.py --limit 100000

# Step B: Data Cleaning, Quality Checks & Feature Engineering
python src/cleaning.py

# Step C: MySQL Schema Initialization & Batch Loading (if MySQL is running)
python src/database.py --load
```

### 4. Launch Streamlit Dashboard
```bash
streamlit run app/dashboard.py
```
*The dashboard will automatically connect to MySQL if available, or seamlessly fall back to `data/cleaned_data.csv` in offline mode.*

---

## 📁 Project Structure

```
Urban_pulse_guvi_project/
├── app/
│   └── dashboard.py               # Streamlit multi-page BI application
├── data/
│   ├── raw_data.csv               # Raw API extract snapshot (100,000 rows)
│   ├── cleaned_data.csv           # Analysis-ready cleaned dataset (100,000 rows)
│   ├── resolution_outliers.csv    # IQR-screened outlier records (16,636 rows)
│   ├── extraction_metadata.json   # API extraction query audit log
│   ├── cleaning_summary.json      # Pipeline validation metrics
│   ├── monthly_population_counts.json # Temporal monthly count cache
│   └── data_dictionary.json       # JSON metadata schema
├── docs/
│   ├── data_dictionary.md         # Field-level analytical data dictionary
│   ├── cleaning_log.md            # Data cleaning and validation log
│   └── analyst_investigations.md  # Detailed report on all 15 core tasks
├── notebooks/
│   ├── 01_data_extraction.ipynb   # API extraction walkthrough
│   ├── 02_data_cleaning.ipynb     # Cleaning & feature engineering notebook
│   └── 03_eda.ipynb               # 15 analyst tasks & statistical EDA
├── sql/
│   ├── schema.sql                 # Database, staging & production DDL
│   └── analysis_queries.sql       # 15 core analyst SQL queries
├── src/
│   ├── extraction.py              # SODA API retrieval module with retries
│   ├── cleaning.py                # Cleaning & feature engineering pipeline
│   └── database.py                # MySQL staging, validation & upsert engine
├── scripts/
│   └── run_full_pipeline.py       # Master automated pipeline runner
├── tests/
│   └── test_database_pipeline.py  # Automated integration & validation tests
├── requirements.txt               # Python package dependencies
├── .env.example                   # Database environment template
├── .gitignore                     # Git ignore rules
└── README.md                      # Comprehensive project documentation
```

---

## ⚠️ Limitations & Responsible Interpretation
- **Reporting vs. Reality:** 311 captures citizen inquiries, reflecting public awareness and digital channel adoption. Lack of reports in an area does not guarantee the absence of underlying infrastructure issues.
- **Resolution Times Skewness:** Non-normal, right-skewed data invalidates ordinary linear assumptions. The median is the primary indicator of typical service turnaround.
- **Operational Closure vs. Satisfaction:** A `Closed` ticket indicates administrative task completion; it does not guarantee permanent problem resolution or resident satisfaction.
- **Cross-Agency Comparisons:** Differing turnaround speeds reflect distinct operational scopes (e.g. mobile police patrol vs. tenant plaster repair) rather than departmental efficiency differences.

---

**Developed for the GUVI Data Analytics & Data Science Capstone Program.**
