# URBAN PULSE: Dataset Data Dictionary

| Field Name | Data Type | Null Count | Null % | Meaning & Description | Transformation & Analytical Use |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `unique_key` | `int64` | 0 | 0.0% | Unique identifier assigned to each 311 service request | Primary Key, distinct request counts |
| `created_date` | `datetime64[us]` | 0 | 0.0% | Date and time when the service request was submitted | Temporal trend analysis, resolution calculation |
| `closed_date` | `datetime64[us]` | 1,608 | 1.61% | Date and time when the service request was officially marked closed | Closure rate and resolution duration computation |
| `resolution_action_updated_date` | `datetime64[us]` | 1,078 | 1.08% | Date and time when resolution action was last recorded | Agency responsiveness tracking |
| `agency` | `object` | 0 | 0.0% | Acronym of the responsible civic agency (e.g., NYPD, HPD, DSNY) | Workload distribution, inter-agency resolution comparison |
| `agency_name` | `object` | 0 | 0.0% | Full formal title of the responsible municipal department | Reporting and dashboard labels |
| `complaint_type` | `object` | 0 | 0.0% | Primary category classification of the service issue | Complaint ranking, prioritization matrix, service mix |
| `descriptor` | `object` | 3,196 | 3.2% | Detailed specification of the complaint | Root cause inspection, detailed filtering |
| `location_type` | `object` | 12,629 | 12.63% | Type of property or environment where the incident occurred | Spatial vulnerability analysis |
| `incident_zip` | `float64` | 1,581 | 1.58% | Five-digit postal zip code of the incident location | Neighborhood-level aggregation |
| `incident_address` | `object` | 5,076 | 5.08% | Physical street number and name of the incident | Micro-location investigations |
| `street_name` | `object` | 5,078 | 5.08% | Name of the street where incident occurred | Corridor analysis |
| `city` | `object` | 5,618 | 5.62% | Municipality / borough neighborhood name | Geographic filtering |
| `status` | `object` | 0 | 0.0% | Operational lifecycle state (Closed, In Progress, Open, Assigned) | Status distribution, backlog tracking |
| `borough` | `object` | 143 | 0.14% | One of the five NYC boroughs or Unspecified | Borough comparisons, geographic demand distribution |
| `latitude` | `float64` | 1,789 | 1.79% | WGS84 latitude coordinate in decimal degrees | Geospatial mapping and clustering |
| `longitude` | `float64` | 1,789 | 1.79% | WGS84 longitude coordinate in decimal degrees | Geospatial mapping and clustering |
| `due_date` | `datetime64[us]` | 99,597 | 99.6% | Service level agreement date when action was expected | SLA tracking and timeliness |
| `descriptor_2` | `object` | 100,000 | 100.0% | Secondary complaint descriptor or sub-category | Sub-issue classification |
| `resolution_description` | `object` | 100,000 | 100.0% | Official explanation of agency findings and action taken | Civic communication review, operational audit |
| `community_board` | `object` | 100,000 | 100.0% | NYC Community Board administrative district identifier | Civic governance reporting |
| `council_district` | `object` | 100,000 | 100.0% | NYC City Council district identifier | Policy and legislative resource allocation |
| `police_precinct` | `object` | 100,000 | 100.0% | NYPD police precinct jurisdiction | Public safety coordination |
| `open_data_channel_type` | `object` | 100,000 | 100.0% | Intake channel (PHONE, ONLINE, MOBILE, OTHER) | Channel adoption and citizen contact preference |
| `park_borough` | `object` | 100,000 | 100.0% | Borough associated with park or public recreation facility | Recreational infrastructure maintenance |
| `is_closed` | `bool` | 0 | 0.0% | Boolean flag: True if record has valid closed_date, False otherwise | Closure rate calculation |
| `resolution_hours` | `float64` | 1,745 | 1.75% | Derived elapsed time in hours between created_date and closed_date | Core KPI, agency performance, IQR outlier detection |
| `is_valid_resolution` | `bool` | 0 | 0.0% | Boolean flag: True if resolution duration is non-negative and valid | Valid sample filtering for statistical metrics |
| `duration_category` | `str` | 0 | 0.0% | Categorical bin: Under 24h, 24-72h, Over 72h, or Unresolved | Operational tier analysis and SLA monitoring |
| `created_year` | `int32` | 0 | 0.0% | Calendar year extracted from created_date | Annual trend analysis |
| `created_month` | `int32` | 0 | 0.0% | Calendar month number (1-12) extracted from created_date | Seasonality analysis |
| `created_month_name` | `str` | 0 | 0.0% | Full month name (e.g. January, February) from created_date | Dashboard monthly timeline visualization |
| `created_weekday` | `str` | 0 | 0.0% | Day of week (Monday-Sunday) from created_date | Weekly demand patterning |
| `created_hour` | `int32` | 0 | 0.0% | Hour of the day (0-23) from created_date | Hourly peak load identification |
| `is_resolution_outlier` | `bool` | 0 | 0.0% | Boolean flag: True if resolution_hours falls outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] | Outlier screening and long-tail case investigation |