/**
 * useSSE — Custom React hook for consuming Server-Sent Events.
 *
 * Usage:
 *   const { data, status, error } = useSSE('/api/rag/query/stream', { query, document_ids });
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { getAuthToken } from '../lib/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type SSEStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

export interface SSEEvent {
    data: string;
    parsed: unknown;
}

export interface UseSSEOptions {
    /** POST body (if provided, sends POST request instead of GET) */
    body?: Record<string, unknown>;
    /** Auto-start the stream */
    autoStart?: boolean;
    /** Callback for each parsed event */
    onEvent?: (event: SSEEvent) => void;
    /** Callback when stream completes */
    onComplete?: (events: SSEEvent[]) => void;
}

export interface UseSSEReturn {
    events: SSEEvent[];
    status: SSEStatus;
    error: string | null;
    start: () => void;
    stop: () => void;
    /** Accumulated text from all data events (useful for token streaming) */
    text: string;
}

export function useSSE(path: string, options: UseSSEOptions = {}): UseSSEReturn {
    const { body, autoStart = false, onEvent, onComplete } = options;

    const [events, setEvents] = useState<SSEEvent[]>([]);
    const [status, setStatus] = useState<SSEStatus>('idle');
    const [error, setError] = useState<string | null>(null);
    const [text, setText] = useState('');

    const controllerRef = useRef<AbortController | null>(null);
    const eventsRef = useRef<SSEEvent[]>([]);

    const stop = useCallback(() => {
        if (controllerRef.current) {
            controllerRef.current.abort();
            controllerRef.current = null;
        }
    }, []);

    const start = useCallback(() => {
        stop();
        setEvents([]);
        setText('');
        setError(null);
        setStatus('connecting');
        eventsRef.current = [];

        const controller = new AbortController();
        controllerRef.current = controller;

        const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
        const token = getAuthToken();

        const fetchOptions: RequestInit = {
            signal: controller.signal,
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...(body ? { 'Content-Type': 'application/json' } : {}),
            },
        };

        if (body) {
            fetchOptions.method = 'POST';
            fetchOptions.body = JSON.stringify(body);
        }

        fetch(url, fetchOptions)
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                setStatus('streaming');
                const reader = response.body?.getReader();
                const decoder = new TextDecoder();

                if (!reader) {
                    throw new Error('No response body');
                }

                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (line.startsWith('data:')) {
                            const data = line.slice(5).trim();
                            if (!data) continue;

                            let parsed: unknown = data;
                            try {
                                parsed = JSON.parse(data);
                            } catch {
                                // plain text token
                            }

                            const event: SSEEvent = { data, parsed };
                            eventsRef.current.push(event);

                            setEvents((prev) => [...prev, event]);

                            // If it's a plain string token, accumulate text
                            if (typeof parsed === 'string') {
                                setText((prev) => prev + parsed);
                            }

                            onEvent?.(event);
                        }
                    }
                }

                setStatus('done');
                onComplete?.(eventsRef.current);
            })
            .catch((err) => {
                if (err.name === 'AbortError') {
                    setStatus('done');
                } else {
                    setStatus('error');
                    setError(err.message);
                }
            });
    }, [path, body, stop, onEvent, onComplete]);

    useEffect(() => {
        if (autoStart) {
            start();
        }
        return stop;
    }, [autoStart, start, stop]);

    return { events, status, error, start, stop, text };
}
