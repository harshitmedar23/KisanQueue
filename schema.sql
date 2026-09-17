-- Reference schema for MySQL deployments.
-- Note: by default this app runs on SQLite and creates tables automatically
-- via SQLAlchemy (db.create_all()) on first run — you do NOT need to run
-- this file for local/demo use. Use it only if you want to provision a
-- MySQL database up front.

CREATE DATABASE IF NOT EXISTS farmer_procurement_prod;
USE farmer_procurement_prod;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    mobile_number VARCHAR(15) NOT NULL UNIQUE,
    email VARCHAR(120),
    role VARCHAR(20) NOT NULL DEFAULT 'farmer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_centre_id INT,
    telegram_chat_id VARCHAR(32) UNIQUE,
    telegram_link_code VARCHAR(10) UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    mobile_number VARCHAR(15) NOT NULL,
    code VARCHAR(6) NOT NULL,
    purpose VARCHAR(20) NOT NULL,
    payload TEXT,
    expires_at DATETIME NOT NULL,
    consumed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS centres (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    location VARCHAR(200),
    latitude FLOAT,
    longitude FLOAT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS slot_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    centre_id INT NOT NULL,
    date DATE NOT NULL,
    time_slot VARCHAR(50) NOT NULL,
    capacity INT NOT NULL DEFAULT 20,
    booked_count INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_centre_date_slot (centre_id, date, time_slot),
    FOREIGN KEY (centre_id) REFERENCES centres(id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id INT NOT NULL,
    centre_id INT NOT NULL,
    slot_config_id INT NOT NULL,
    crop_type VARCHAR(80) NOT NULL,
    quantity_kg FLOAT NOT NULL,
    token_number INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'booked',
    approval_status VARCHAR(20) NOT NULL DEFAULT 'approved',
    rejection_reason VARCHAR(200),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    payment_amount FLOAT,
    payment_method VARCHAR(20),
    payment_reference VARCHAR(120),
    turn_soon_notified BOOLEAN NOT NULL DEFAULT FALSE,
    booked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    serving_started_at DATETIME,
    completed_at DATETIME,
    paid_at DATETIME,
    approved_at DATETIME,
    checkin_token VARCHAR(64) UNIQUE,
    checked_in_at DATETIME,
    FOREIGN KEY (farmer_id) REFERENCES users(id),
    FOREIGN KEY (centre_id) REFERENCES centres(id),
    FOREIGN KEY (slot_config_id) REFERENCES slot_configs(id)
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    driver_name VARCHAR(120) NOT NULL,
    driver_phone VARCHAR(15) NOT NULL,
    capacity_kg FLOAT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    centre_id INT,
    driver_status VARCHAR(20) NOT NULL DEFAULT 'available',
    assigned_booking_id INT
);

CREATE TABLE IF NOT EXISTS transport_bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    vehicle_id INT,
    pickup_location TEXT NOT NULL,
    estimated_distance_km FLOAT,
    fare_amount FLOAT NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    status VARCHAR(20) NOT NULL DEFAULT 'requested',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message VARCHAR(500) NOT NULL,
    category VARCHAR(30) DEFAULT 'info',
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subscription_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mandi_prices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    centre_id INT,
    crop_type VARCHAR(80) NOT NULL,
    market_name VARCHAR(120) NOT NULL,
    msp_per_quintal FLOAT NOT NULL,
    market_price_per_quintal FLOAT NOT NULL,
    effective_date DATE NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_mandi_prices_crop_type (crop_type),
    INDEX ix_mandi_prices_centre_id (centre_id),
    FOREIGN KEY (centre_id) REFERENCES centres(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    actor_id INT,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INT,
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_audit_logs_created_at (created_at),
    FOREIGN KEY (actor_id) REFERENCES users(id)
);
