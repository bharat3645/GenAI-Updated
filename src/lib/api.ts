/**
 * API Client — Central HTTP client for communicating with the API Gateway.
 *
 * All service calls go through http://localhost:8000/api/*
 * Authentication is handled via JWT Bearer tokens.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Token Management ───────────────────────────────────────────

let authToken: string | null = localStorage.getItem('genai_token');

export function setAuthToken(token: string) {
    authToken = token;
    localStorage.setItem('genai_token', token);
}

export function clearAuthToken() {
    authToken = null;
    localStorage.removeItem('genai_token');
}

export function getAuthToken(): string | null {
    return authToken;
}

// ── HTTP Helpers ───────────────────────────────────────────────

function headers(extra: Record<string, string> = {}): Record<string, string> {
    const h: Record<string, string> = { ...extra };
    if (authToken) {
        h['Authorization'] = `Bearer ${authToken}`;
    }
    return h;
}

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(body.detail || body.error || `HTTP ${response.status}`);
    }
    return response.json();
}

// ── Auth ───────────────────────────────────────────────────────

export async function apiLogin(email: string, password: string) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ email, password }),
    });
    const data = await handleResponse<{ token: string; user_id: string; email: string }>(res);
    setAuthToken(data.token);
    return data;
}

export async function apiRegister(email: string, password: string, displayName: string = '') {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ email, password, display_name: displayName }),
    });
    const data = await handleResponse<{ token: string; user_id: string; email: string }>(res);
    setAuthToken(data.token);
    return data;
}

// ── RAG Service ────────────────────────────────────────────────

export async function ragIngest(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/api/rag/ingest`, {
        method: 'POST',
        headers: headers(),
        body: formData,
    });
    return handleResponse<{
        document_id: string;
        filename: string;
        chunk_count: number;
        entity_count: number;
        relationship_count: number;
        message: string;
    }>(res);
}

export async function ragQuery(query: string, documentIds: string[], useGraph = true) {
    const res = await fetch(`${API_BASE}/api/rag/query`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ query, document_ids: documentIds, use_graph: useGraph }),
    });
    return handleResponse<{
        answer: string;
        sources: Array<{ chunk_id: string; content: string; score: number; document_id: string }>;
        graph_context: Array<{ subject: string; predicate: string; obj: string }>;
    }>(res);
}

export function ragQueryStream(query: string, documentIds: string[], useGraph = true) {
    return createSSEStream(`${API_BASE}/api/rag/query/stream`, {
        query,
        document_ids: documentIds,
        use_graph: useGraph,
    });
}

export async function ragGetGraph(docId: string) {
    const res = await fetch(`${API_BASE}/api/rag/graph/${docId}`, {
        headers: headers(),
    });
    return handleResponse<{
        nodes: Array<{ id: string; label: string; type: string; properties: Record<string, unknown> }>;
        edges: Array<{ source: string; target: string; label: string }>;
    }>(res);
}

// ── ATS Service ────────────────────────────────────────────────

export async function atsAnalyze(resumeText: string, jobDescription: string = '') {
    const res = await fetch(`${API_BASE}/api/ats/analyze`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ resume_text: resumeText, job_description: jobDescription }),
    });
    return handleResponse<{ task_id: string; report: ATSReport }>(res);
}

export function atsAnalyzeStream(resumeText: string, jobDescription: string = '') {
    return createSSEStream(`${API_BASE}/api/ats/analyze/stream`, {
        resume_text: resumeText,
        job_description: jobDescription,
    });
}

export interface ATSReport {
    score: number;
    breakdown: {
        keyword_relevance: number;
        formatting_compliance: number;
        content_quality: number;
        weighted_score: number;
    };
    keywords_found: string[];
    keywords_missing: string[];
    formatting_issues: string[];
    content_suggestions: string[];
    action_verbs_found: string[];
    quantifiable_metrics: string[];
    summary: string;
}

// ── Research Service ───────────────────────────────────────────

export async function researchStart(query: string, depth: string = 'standard') {
    const res = await fetch(`${API_BASE}/api/research/start`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ query, depth }),
    });
    return handleResponse<{
        task_id: string;
        status: string;
        report: string;
        sources: ResearchSource[];
    }>(res);
}

export async function researchGetReport(taskId: string) {
    const res = await fetch(`${API_BASE}/api/research/report/${taskId}`, {
        headers: headers(),
    });
    return handleResponse<{
        task_id: string;
        query: string;
        status: string;
        report: string;
        sources: ResearchSource[];
    }>(res);
}

export interface ResearchSource {
    id: string;
    title: string;
    url: string;
    snippet: string;
    verified: boolean;
}

// ── SQL Service ────────────────────────────────────────────────

export async function sqlGenerate(query: string) {
    const res = await fetch(`${API_BASE}/api/sql/generate`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ query }),
    });
    return handleResponse<{
        natural_language: string;
        generated_sql: string;
        safe: boolean;
        safety_details: Record<string, unknown>;
    }>(res);
}

export async function sqlExecute(sql: string) {
    const res = await fetch(`${API_BASE}/api/sql/execute`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ sql }),
    });
    return handleResponse<{
        columns: string[];
        rows: unknown[][];
        row_count: number;
        truncated: boolean;
    }>(res);
}

export async function sqlGetSchema() {
    const res = await fetch(`${API_BASE}/api/sql/schema`, {
        headers: headers(),
    });
    return handleResponse<{
        tables: Array<{
            name: string;
            columns: Array<{ name: string; type: string; nullable: boolean }>;
        }>;
    }>(res);
}

// ── Gateway Health ─────────────────────────────────────────────

export async function getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<{
        status: string;
        services: Record<string, string>;
        timestamp: string;
    }>(res);
}

// ── SSE Helper ─────────────────────────────────────────────────

export interface SSEStream {
    onMessage: (callback: (data: string) => void) => void;
    onError: (callback: (error: Event) => void) => void;
    close: () => void;
}

function createSSEStream(url: string, body: Record<string, unknown>): SSEStream {
    const controller = new AbortController();

    let messageCallback: ((data: string) => void) | null = null;
    let errorCallback: ((error: Event) => void) | null = null;

    // Start the fetch
    fetch(url, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: controller.signal,
    })
        .then(async (response) => {
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) return;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value, { stream: true });
                const lines = text.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data:')) {
                        const data = line.slice(5).trim();
                        if (data && messageCallback) {
                            messageCallback(data);
                        }
                    }
                }
            }
        })
        .catch((err) => {
            if (err.name !== 'AbortError' && errorCallback) {
                errorCallback(err);
            }
        });

    return {
        onMessage: (cb) => { messageCallback = cb; },
        onError: (cb) => { errorCallback = cb; },
        close: () => controller.abort(),
    };
}

// ── Stats ──────────────────────────────────────────────────────

export async function apiGetStats(): Promise<{ documents: number; reports: number; queries: number }> {
    const res = await fetch(`${API_BASE}/api/stats`, {
        headers: headers(),
    });
    return handleResponse(res);
}
