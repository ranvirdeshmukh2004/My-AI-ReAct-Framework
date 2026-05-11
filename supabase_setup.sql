-- ============================================
-- AI Agent — Supabase PostgreSQL Schema
-- ============================================
-- Run this in your Supabase SQL Editor:
-- https://app.supabase.com → Your Project → SQL Editor
-- ============================================

-- Messages table (conversation history)
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast session lookups
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);

-- Index for listing sessions by recency
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);

-- Enable Row Level Security (RLS) — optional but good practice
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow all" ON messages FOR ALL USING (true);
