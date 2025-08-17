'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id: number;
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<boolean>;
  signup: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  loading: boolean;
}

const API_BASE = ''; // Use relative URLs, nginx will proxy to API backend

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token in localStorage
    const storedToken = localStorage.getItem('auth_token');
    console.log('AuthContext: Checking for stored token:', storedToken ? 'Found' : 'Not found');
    
    if (storedToken) {
      setToken(storedToken);
      // Extract user info from stored token
      try {
        const payload = JSON.parse(atob(storedToken.split('.')[1]));
        setUser({ id: parseInt(payload.sub), email: payload.email || 'user@example.com' });
        console.log('AuthContext: User restored from token:', payload.sub);
      } catch (e) {
        console.error('Error parsing stored JWT token:', e);
        // If token is corrupted, remove it
        localStorage.removeItem('auth_token');
        setToken(null);
        setUser(null);
      }
      setLoading(false);
    } else {
      setLoading(false);
    }
  }, []);

  const signup = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/v1/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (response.ok) {
        const data = await response.json();
        const newToken = data.access_token;
        
        setToken(newToken);
        localStorage.setItem('auth_token', newToken);
        
        // Extract user ID from JWT token (simple parsing)
        try {
          const payload = JSON.parse(atob(newToken.split('.')[1]));
          setUser({ id: parseInt(payload.sub), email });
        } catch (e) {
          console.error('Error parsing JWT token:', e);
        }
        
        return true;
      }
      return false;
    } catch (error) {
      console.error('Signup error:', error);
      return false;
    }
  };

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (response.ok) {
        const data = await response.json();
        const newToken = data.access_token;
        
        setToken(newToken);
        localStorage.setItem('auth_token', newToken);
        
        // Extract user ID from JWT token
        try {
          const payload = JSON.parse(atob(newToken.split('.')[1]));
          setUser({ id: parseInt(payload.sub), email });
        } catch (e) {
          console.error('Error parsing JWT token:', e);
        }
        
        return true;
      }
      return false;
    } catch (error) {
      console.error('Login error:', error);
      return false;
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('auth_token');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, signup, logout, loading }}>
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
