import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { apiLogin, apiRegister, clearAuthToken, getAuthToken } from '../lib/api';

// ── Types ──────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error?: string }>;
  signUp: (email: string, password: string, displayName?: string) => Promise<{ error?: string }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ── Helper: decode JWT payload without a library ───────────────

function decodeJwtPayload(token: string): { sub: string; email: string; exp: number } | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

// ── Provider ───────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount, restore session from localStorage token
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      const payload = decodeJwtPayload(token);
      if (payload && payload.exp * 1000 > Date.now()) {
        setUser({ id: payload.sub, email: payload.email });
      } else {
        // Token is expired or invalid
        clearAuthToken();
      }
    }
    setLoading(false);
  }, []);

  const signIn = async (email: string, password: string): Promise<{ error?: string }> => {
    try {
      const data = await apiLogin(email, password);
      setUser({ id: data.user_id, email: data.email });
      return {};
    } catch (err: any) {
      return { error: err.message || 'Login failed' };
    }
  };

  const signUp = async (email: string, password: string, displayName?: string): Promise<{ error?: string }> => {
    try {
      const data = await apiRegister(email, password, displayName || '');
      setUser({ id: data.user_id, email: data.email });
      return {};
    } catch (err: any) {
      return { error: err.message || 'Registration failed' };
    }
  };

  const signOut = async () => {
    clearAuthToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
