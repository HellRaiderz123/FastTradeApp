import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { authAPI, authTokenStore } from '../lib/api';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = authTokenStore.get();
    
    if (!token) {
      setIsAuthenticated(false);
      setLoading(false);
      return;
    }

    try {
      // Verify token is still valid by calling /auth/me
      await authAPI.me();
      setIsAuthenticated(true);
    } catch (error) {
      // Token is invalid or expired
      authTokenStore.clear();
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen terminal-shell">
        <div className="text-terminal-green">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-terminal-green"></div>
        </div>
      </div>
    );
  }

  if (isAuthenticated === false) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
