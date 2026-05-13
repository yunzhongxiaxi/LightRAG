-- Prompt Management System Database Schema
-- Migration: 001_create_prompt_tables
-- Description: Create tables for prompt templates, versions, and user configurations

-- Prompt templates table
CREATE TABLE IF NOT EXISTS prompt_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    type VARCHAR(50) NOT NULL CHECK (type IN ('system', 'user', 'shared')),
    content JSONB NOT NULL,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_template BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Prompt versions table (for version history)
CREATE TABLE IF NOT EXISTS prompt_versions (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    comment TEXT,
    created_by VARCHAR(255),
    UNIQUE(template_id, version)
);

-- User prompt configurations (tracks which template each user is using)
CREATE TABLE IF NOT EXISTS user_prompt_configs (
    user_id VARCHAR(255) PRIMARY KEY,
    template_id INTEGER REFERENCES prompt_templates(id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prompt_templates_type ON prompt_templates(type);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_created_by ON prompt_templates(created_by);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_is_active ON prompt_templates(is_active);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_template_id ON prompt_versions(template_id);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_created_at ON prompt_versions(created_at DESC);

-- Trigger to auto-increment version number
CREATE OR REPLACE FUNCTION increment_prompt_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version := COALESCE(
        (SELECT MAX(version) FROM prompt_versions WHERE template_id = NEW.template_id),
        0
    ) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_increment_version
BEFORE INSERT ON prompt_versions
FOR EACH ROW
EXECUTE FUNCTION increment_prompt_version();

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_prompt_templates_updated_at
BEFORE UPDATE ON prompt_templates
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_prompt_configs_updated_at
BEFORE UPDATE ON user_prompt_configs
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
