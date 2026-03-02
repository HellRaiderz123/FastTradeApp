import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, authTokenStore } from '../lib/api';

function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authAPI.login(username, password);
      const { access_token } = response.data;
      
      // Store token
      authTokenStore.set(access_token);
      
      // Navigate to dashboard
      navigate('/');
    } catch (err: any) {
      console.error('Login failed:', err);
      
      if (err.response?.status === 401) {
        setError('Invalid username or password');
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center terminal-shell p-4">
      <div className="w-full max-w-md">
        <div className="panel p-8">
          {/* Logo/Title */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-terminal-green mb-2">
              FastTrade Terminal
            </h1>
            <p className="text-slate-400">
              Sign in to access your trading platform
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/50">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-300 mb-2">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg 
                           text-white placeholder-slate-500 focus:outline-none focus:ring-2 
                           focus:ring-terminal-green focus:border-transparent"
                placeholder="Enter username"
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg 
                           text-white placeholder-slate-500 focus:outline-none focus:ring-2 
                           focus:ring-terminal-green focus:border-transparent"
                placeholder="Enter password"
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-terminal-green hover:bg-green-600 text-slate-900 
                         font-semibold rounded-lg transition-colors disabled:opacity-50 
                         disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-8 text-center text-sm text-slate-500">
            <p>Secured by FastTradeApp Authentication</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
