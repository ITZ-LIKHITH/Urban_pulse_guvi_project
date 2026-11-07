-- =====================================================================
-- URBAN PULSE: Citizen Complaint Intelligence & Resolution Analytics
-- Database Schema Definition (MySQL)
-- Database: urban_pulse_db
-- Tables: staging_service_requests, service_requests
-- =====================================================================

CREATE DATABASE IF NOT EXISTS urban_pulse_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE urban_pulse_db;

-- ---------------------------------------------------------------------
-- 1. STAGING TABLE: staging_service_requests
-- Used for fast, resilient, unconstrained bulk ingestion
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS staging_service_requests;

CREATE TABLE staging_service_requests (
    unique_key BIGINT NOT NULL,
    created_date DATETIME NULL,
    closed_date DATETIME NULL,
    due_date DATETIME NULL,
    resolution_action_updated_date DATETIME NULL,
    agency VARCHAR(50) NULL,
    agency_name VARCHAR(255) NULL,
    complaint_type VARCHAR(150) NULL,
    descriptor VARCHAR(255) NULL,
    descriptor_2 VARCHAR(255) NULL,
    location_type VARCHAR(150) NULL,
    incident_zip VARCHAR(20) NULL,
    incident_address VARCHAR(255) NULL,
    street_name VARCHAR(150) NULL,
    city VARCHAR(100) NULL,
    status VARCHAR(50) NULL,
    resolution_description TEXT NULL,
    community_board VARCHAR(100) NULL,
    council_district VARCHAR(20) NULL,
    police_precinct VARCHAR(100) NULL,
    borough VARCHAR(50) NULL,
    open_data_channel_type VARCHAR(50) NULL,
    park_borough VARCHAR(50) NULL,
    latitude DECIMAL(10, 7) NULL,
    longitude DECIMAL(10, 7) NULL,
    resolution_hours DECIMAL(10, 2) NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    is_valid_resolution BOOLEAN DEFAULT FALSE,
    duration_category VARCHAR(50) NULL,
    created_year INT NULL,
    created_month INT NULL,
    created_month_name VARCHAR(20) NULL,
    created_weekday VARCHAR(20) NULL,
    created_hour INT NULL,
    is_resolution_outlier BOOLEAN DEFAULT FALSE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 2. PRODUCTION TABLE: service_requests
-- Target analytical table with constraints and optimized query indexes
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS service_requests;

CREATE TABLE IF NOT EXISTS service_requests (
    unique_key BIGINT NOT NULL,
    created_date DATETIME NOT NULL,
    closed_date DATETIME NULL,
    due_date DATETIME NULL,
    resolution_action_updated_date DATETIME NULL,
    agency VARCHAR(50) NOT NULL,
    agency_name VARCHAR(255) NULL,
    complaint_type VARCHAR(150) NOT NULL,
    descriptor VARCHAR(255) NULL,
    descriptor_2 VARCHAR(255) NULL,
    location_type VARCHAR(150) NULL,
    incident_zip VARCHAR(20) NULL,
    incident_address VARCHAR(255) NULL,
    street_name VARCHAR(150) NULL,
    city VARCHAR(100) NULL,
    status VARCHAR(50) NOT NULL,
    resolution_description TEXT NULL,
    community_board VARCHAR(100) NULL,
    council_district VARCHAR(20) NULL,
    police_precinct VARCHAR(100) NULL,
    borough VARCHAR(50) NULL DEFAULT 'Unspecified',
    open_data_channel_type VARCHAR(50) NULL,
    park_borough VARCHAR(50) NULL,
    latitude DECIMAL(10, 7) NULL,
    longitude DECIMAL(10, 7) NULL,
    resolution_hours DECIMAL(10, 2) NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    is_valid_resolution BOOLEAN DEFAULT FALSE,
    duration_category VARCHAR(50) NULL,
    created_year INT NULL,
    created_month INT NULL,
    created_month_name VARCHAR(20) NULL,
    created_weekday VARCHAR(20) NULL,
    created_hour INT NULL,
    is_resolution_outlier BOOLEAN DEFAULT FALSE,
    ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (unique_key),
    INDEX idx_created_date (created_date),
    INDEX idx_agency (agency),
    INDEX idx_complaint_type (complaint_type),
    INDEX idx_borough (borough),
    INDEX idx_status (status),
    INDEX idx_resolution_hours (resolution_hours),
    INDEX idx_agency_status (agency, status),
    INDEX idx_year_month (created_year, created_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

