-- Chowkidaar NVR - Database Initialization Script
-- This script creates all required tables and indexes

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- User roles enum
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'operator', 'viewer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Camera status enum
DO $$ BEGIN
    CREATE TYPE camera_status AS ENUM ('online', 'offline', 'connecting', 'error', 'disabled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Camera type enum
DO $$ BEGIN
    CREATE TYPE camera_type AS ENUM ('rtsp', 'http', 'onvif');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Event type enum (includes LLM-classified intelligent types)
DO $$ BEGIN
    CREATE TYPE event_type AS ENUM (
        -- Basic detections (YOLO)
        'person_detected', 'vehicle_detected', 'animal_detected', 'motion_detected',
        
        -- Intelligent classifications (LLM decides)
        'delivery',           -- Delivery person, courier, postman, food delivery
        'visitor',            -- Guest, friend, family member visiting
        'package_left',       -- Package/parcel left at door
        'suspicious',         -- Suspicious behavior, lurking, unknown person
        'intrusion',          -- Unauthorized entry attempt
        'loitering',          -- Person staying too long without purpose
        'theft_attempt',      -- Stealing, taking items
        
        -- Emergency
        'fire_detected', 'smoke_detected',
        
        -- Other
        'custom'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Event severity enum
DO $$ BEGIN
    CREATE TYPE event_severity AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ===========================================
-- USERS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role user_role DEFAULT 'viewer' NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    last_login TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ===========================================
-- CAMERAS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS cameras (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    stream_url VARCHAR(500) NOT NULL,
    camera_type camera_type DEFAULT 'rtsp',
    username VARCHAR(100),
    password VARCHAR(255),
    status camera_status DEFAULT 'offline',
    last_seen TIMESTAMP,
    error_message TEXT,
    is_enabled BOOLEAN DEFAULT true,
    detection_enabled BOOLEAN DEFAULT true,
    recording_enabled BOOLEAN DEFAULT false,
    fps INTEGER DEFAULT 15,
    resolution_width INTEGER,
    resolution_height INTEGER,
    location VARCHAR(255),
    
    -- Context-aware detection settings (helps AI decide severity)
    location_type VARCHAR(100),              -- office, kitchen, warehouse, entrance, parking, etc.
    expected_activity TEXT,                   -- "people working on computers", "cooking with fire"
    unexpected_activity TEXT,                 -- "running", "fighting", "strangers at night"
    normal_conditions TEXT,                   -- "5-10 people during work hours", "fire on stove is normal"
    
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cameras_owner ON cameras(owner_id);
CREATE INDEX IF NOT EXISTS idx_cameras_status ON cameras(status);

-- ===========================================
-- EVENTS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_type event_type NOT NULL,
    severity event_severity DEFAULT 'low' NOT NULL,
    detected_objects JSONB DEFAULT '[]',
    confidence_score FLOAT DEFAULT 0.0,
    frame_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    detection_metadata JSONB DEFAULT '{}',
    summary TEXT,
    summary_generated_at TIMESTAMP,
    timestamp TIMESTAMP DEFAULT NOW() NOT NULL,
    duration_seconds FLOAT,
    is_acknowledged BOOLEAN DEFAULT false,
    acknowledged_at TIMESTAMP,
    acknowledged_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_events_acknowledged ON events(is_acknowledged);

-- ===========================================
-- CHAT SESSIONS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);

-- ===========================================
-- CHAT MESSAGES TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    message_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- ===========================================
-- USER SETTINGS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Detection settings
    detection_model VARCHAR(100) DEFAULT 'yolov8n',
    detection_confidence FLOAT DEFAULT 0.5,
    detection_device VARCHAR(50) DEFAULT 'cuda',
    enabled_classes JSONB DEFAULT '["person", "car", "truck", "dog", "cat"]',
    
    -- VLM settings
    vlm_model VARCHAR(100) DEFAULT 'gemma3:4b',
    vlm_url VARCHAR(255) DEFAULT 'http://localhost:11434',
    auto_summarize BOOLEAN DEFAULT true,
    summarize_delay INTEGER DEFAULT 5,
    vlm_safety_scan_enabled BOOLEAN DEFAULT true,
    vlm_safety_scan_interval INTEGER DEFAULT 30,
    
    -- Storage settings
    recordings_path VARCHAR(500) DEFAULT '/data/recordings',
    snapshots_path VARCHAR(500) DEFAULT '/data/snapshots',
    max_storage_gb INTEGER DEFAULT 500,
    retention_days INTEGER DEFAULT 30,
    
    -- Notification settings
    notifications_enabled BOOLEAN DEFAULT true,
    min_severity VARCHAR(20) DEFAULT 'high',
    notify_event_types JSONB DEFAULT '["all"]',
    
    -- Telegram settings
    telegram_enabled BOOLEAN DEFAULT false,
    telegram_bot_token VARCHAR(255),
    telegram_chat_id VARCHAR(100),
    telegram_send_photo BOOLEAN DEFAULT true,
    telegram_send_summary BOOLEAN DEFAULT true,
    telegram_send_details BOOLEAN DEFAULT true,
    
    -- Email settings
    email_enabled BOOLEAN DEFAULT false,
    email_smtp_host VARCHAR(255),
    email_smtp_port INTEGER DEFAULT 587,
    email_smtp_user VARCHAR(255),
    email_smtp_password VARCHAR(255),
    email_from_address VARCHAR(255),
    email_recipients JSONB DEFAULT '[]',
    email_send_photo BOOLEAN DEFAULT true,
    email_send_summary BOOLEAN DEFAULT true,
    email_send_details BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(user_id);

-- ===========================================
-- FUNCTIONS
-- ===========================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_cameras_updated_at ON cameras;
CREATE TRIGGER update_cameras_updated_at
    BEFORE UPDATE ON cameras
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_settings_updated_at ON user_settings;
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===========================================
-- GRANT PERMISSIONS (for external connections)
-- ===========================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO chowkidaar;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO chowkidaar;

-- ===========================================
-- COMPLETED
-- ===========================================
SELECT 'Chowkidaar NVR database initialized successfully!' as status;
