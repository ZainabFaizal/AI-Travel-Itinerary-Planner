-- ============================================================
--  AI Travel Planner — Database Schema
--  Import this file in phpMyAdmin:
--    Database > Import > Choose File > travel_planner.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS travel_planner
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE travel_planner;

-- ── USERS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    username      VARCHAR(100) NOT NULL PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(200) NOT NULL,
    email         VARCHAR(200) DEFAULT '',
    avatar        VARCHAR(10)  DEFAULT 'U',
    pref_currency VARCHAR(10)  DEFAULT 'USD',
    last_login    DATETIME     DEFAULT NULL,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── ADMINS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admins (
    username      VARCHAR(100) NOT NULL PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(200) NOT NULL,
    email         VARCHAR(200) DEFAULT '',
    last_login    DATETIME     DEFAULT NULL,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── ITINERARIES ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS itineraries (
    id               VARCHAR(36)   NOT NULL PRIMARY KEY,
    user             VARCHAR(100)  NOT NULL,
    destination      VARCHAR(300)  DEFAULT '',
    days             INT           DEFAULT 1,
    start_date       VARCHAR(20)   DEFAULT '',
    budget           DECIMAL(14,2) DEFAULT 0,
    travelers        INT           DEFAULT 1,
    travel_type      VARCHAR(100)  DEFAULT '',
    activities       TEXT,
    notes            TEXT,
    accommodation    VARCHAR(100)  DEFAULT 'Any',
    transport        VARCHAR(100)  DEFAULT 'Any',
    meal_pref        VARCHAR(100)  DEFAULT 'No preference',
    pace             VARCHAR(50)   DEFAULT 'Moderate',
    fitness          VARCHAR(100)  DEFAULT 'Moderate',
    must_visit       TEXT,
    avoid            TEXT,
    group_type       VARCHAR(100)  DEFAULT 'Solo',
    kids_ages        VARCHAR(200)  DEFAULT '',
    eco              TINYINT(1)    DEFAULT 0,
    pet              TINYINT(1)    DEFAULT 0,
    trip_theme       VARCHAR(100)  DEFAULT 'General',
    day_start        VARCHAR(50)   DEFAULT 'Standard (8 am)',
    restaurant_meals INT           DEFAULT 2,
    nightlife        TINYINT(1)    DEFAULT 0,
    off_peak         TINYINT(1)    DEFAULT 0,
    budget_priority  VARCHAR(100)  DEFAULT 'Balanced',
    currency         VARCHAR(10)   DEFAULT 'USD',
    itinerary        LONGTEXT,
    packing_list     LONGTEXT,
    saved_on         VARCHAR(20)   DEFAULT '',
    starred          TINYINT(1)    DEFAULT 0,
    created_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user) REFERENCES users(username) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── EXPENSES ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS expenses (
    id           VARCHAR(36)   NOT NULL PRIMARY KEY,
    itinerary_id VARCHAR(36)   NOT NULL,
    user         VARCHAR(100)  NOT NULL,
    date         VARCHAR(20)   DEFAULT '',
    category     VARCHAR(100)  DEFAULT '',
    description  TEXT,
    amount       DECIMAL(12,2) DEFAULT 0,
    created_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (itinerary_id) REFERENCES itineraries(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── DEFAULT ACCOUNTS ─────────────────────────────────────────
-- Seeded automatically by the app on first run using PBKDF2-SHA256.
-- Admin  (admins table):  admin / Admin@1234
-- User   (users table):   traveler / Travel@123
-- Change default passwords immediately after first login.
-- Admin portal URL:  http://localhost:8501/?portal=admin
