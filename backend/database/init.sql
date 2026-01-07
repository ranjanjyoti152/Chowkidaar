-- Chowkidaar NVR - Database Initialization Script
-- This script creates all required tables and indexes
-- Updated for V-JEPA 2 video understanding

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for semantic search embeddings

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

-- Event type enum (V-JEPA 2 activity recognition)
DO $$ BEGIN
    CREATE TYPE event_type AS ENUM (
        -- Basic detections
        'person_detected', 'vehicle_detected', 'animal_detected', 'motion_detected',
        'object_detected',    -- General objects
        
        -- Activity classifications (V-JEPA 2)
        'person_walking',     -- Person walking detected
        'person_running',     -- Person running detected
        'person_standing',    -- Person standing/stationary
        'person_entering',    -- Person entering area
        'person_leaving',     -- Person leaving area
        'vehicle_moving',     -- Vehicle in motion
        'vehicle_parked',     -- Parked vehicle
        'suspicious_activity', -- Suspicious behavior detected
        'normal_activity',    -- Normal/routine activity
        
        -- Legacy intelligent classifications
        'delivery',           -- Delivery person, courier
        'visitor',            -- Guest, visitor
        'package_left',       -- Package left at door
        'suspicious',         -- Suspicious behavior
        'intrusion',          -- Unauthorized entry attempt
        'loitering',          -- Person staying too long
        'theft_attempt',      -- Stealing attempt
        
        -- Emergency / Safety
        'fire_detected', 'smoke_detected',
        'fall_detected',      -- Person fallen/collapsed
        'accident',           -- Collision, crash
        'medical_emergency',  -- Person needs medical help
        
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
    
    -- Approval system - new users need admin approval
    is_approved BOOLEAN DEFAULT false,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    last_login TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_approved ON users(is_approved);

-- ===========================================
-- USER PERMISSIONS TABLE (RBAC)
-- ===========================================
CREATE TABLE IF NOT EXISTS user_permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Page Access Permissions
    can_access_dashboard BOOLEAN DEFAULT true,
    can_access_cameras BOOLEAN DEFAULT true,
    can_access_events BOOLEAN DEFAULT true,
    can_access_monitor BOOLEAN DEFAULT true,
    can_access_assistant BOOLEAN DEFAULT true,
    can_access_settings BOOLEAN DEFAULT false,
    can_access_admin BOOLEAN DEFAULT false,
    
    -- Camera Permissions
    can_view_cameras BOOLEAN DEFAULT true,
    can_add_cameras BOOLEAN DEFAULT false,
    can_edit_cameras BOOLEAN DEFAULT false,
    can_delete_cameras BOOLEAN DEFAULT false,
    can_control_ptz BOOLEAN DEFAULT false,
    
    -- Event Permissions
    can_view_events BOOLEAN DEFAULT true,
    can_acknowledge_events BOOLEAN DEFAULT false,
    can_delete_events BOOLEAN DEFAULT false,
    can_export_events BOOLEAN DEFAULT true,
    
    -- Settings Permissions
    can_modify_detection_settings BOOLEAN DEFAULT false,
    can_modify_vjepa2_settings BOOLEAN DEFAULT false,   -- V-JEPA 2 settings
    can_modify_notification_settings BOOLEAN DEFAULT false,
    can_modify_system_settings BOOLEAN DEFAULT false,
    
    -- User Management Permissions
    can_view_users BOOLEAN DEFAULT false,
    can_add_users BOOLEAN DEFAULT false,
    can_edit_users BOOLEAN DEFAULT false,
    can_delete_users BOOLEAN DEFAULT false,
    can_change_user_roles BOOLEAN DEFAULT false,
    can_change_user_permissions BOOLEAN DEFAULT false,
    
    -- System Permissions
    can_restart_services BOOLEAN DEFAULT false,
    can_view_system_logs BOOLEAN DEFAULT false,
    can_manage_models BOOLEAN DEFAULT false,
    
    -- Specific camera access (null = all cameras, array = specific camera IDs)
    allowed_camera_ids JSONB DEFAULT NULL,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);

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
    resolution_width INTEGER DEFAULT 640,
    resolution_height INTEGER DEFAULT 480,
    location VARCHAR(255),
    
    -- Context-aware detection settings (helps AI decide severity)
    location_type VARCHAR(100),
    expected_activity TEXT,
    unexpected_activity TEXT,
    normal_conditions TEXT,
    
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
    
    -- Vector Embeddings (pgvector) for semantic search
    text_embedding vector(384),
    image_embedding vector(512),
    
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

-- GIN index for efficient JSONB queries on detected_objects
CREATE INDEX IF NOT EXISTS idx_events_detected_objects ON events USING GIN (detected_objects);

-- HNSW indexes for fast vector similarity search (pgvector)
CREATE INDEX IF NOT EXISTS idx_events_text_embedding 
    ON events USING hnsw (text_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_events_image_embedding 
    ON events USING hnsw (image_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

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
-- USER SETTINGS TABLE (V-JEPA 2)
-- ===========================================
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- V-JEPA 2 Detection settings
    vjepa2_model VARCHAR(100) DEFAULT 'vjepa2-large',
    vjepa2_buffer_size INTEGER DEFAULT 64,       -- Frames in video buffer
    vjepa2_sample_rate INTEGER DEFAULT 4,        -- Sample every Nth frame
    detection_device VARCHAR(50) DEFAULT 'cuda',
    detection_confidence FLOAT DEFAULT 0.5,
    
    -- Legacy fields (for migration compatibility)
    detection_model VARCHAR(100) DEFAULT 'vjepa2-large',
    enabled_classes JSONB DEFAULT '[]',
    
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

DROP TRIGGER IF EXISTS update_user_permissions_updated_at ON user_permissions;
CREATE TRIGGER update_user_permissions_updated_at
    BEFORE UPDATE ON user_permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===========================================
-- COMPLETED
-- ===========================================
SELECT 'Chowkidaar NVR database initialized with V-JEPA 2 support!' as status;
