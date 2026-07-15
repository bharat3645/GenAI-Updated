-- GenAI Platform — PostgreSQL Init (runs on container first start)
-- Database schema for local JWT-based auth and application state.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Users (JWT auth via API Gateway) ──────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── PDF Documents ──────────────────────────────────────CREATE TABLE IF NOT EXISTS pdf_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Chat Sessions ──────────────────────────────────────CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Resume Feedback ──────────────────────────────────CREATE TABLE IF NOT EXISTS resume_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    job_description TEXT,
    ats_score INTEGER CHECK (ats_score >= 0 AND ats_score <= 100),
    report JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Research Tasks ────────────────────────────────────CREATE TABLE IF NOT EXISTS research_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    status TEXT DEFAULT 'planning' CHECK (status IN (
        'planning','searching','filtering','summarizing',
        'verifying','synthesizing','citing','completed','failed'
    )),
    report TEXT,
    sources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ── SQL Query History ───────────────────────────────────CREATE TABLE IF NOT EXISTS sql_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    natural_language TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    executed BOOLEAN DEFAULT FALSE,
    results JSONB,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ──────────────────────────────────────────────CREATE INDEX IF NOT EXISTS idx_pdf_docs_user ON pdf_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sess_user ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_msgs_sess ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_resume_fb_user ON resume_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_research_user ON research_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_research_status ON research_tasks(status);
CREATE INDEX IF NOT EXISTS idx_sql_queries_user ON sql_queries(user_id);
