import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, authTokenStore } from '../lib/api';
import { ExternalLink, CheckCircle, AlertTriangle, ArrowRight, Key, SkipForward } from 'lucide-react';

type Step = 'login' | 'broker';

interface BrokerStatus {
  has_token: boolean;       // true only if token exists AND liveness ping passed
  token_found: boolean;     // token string exists in DB/env
  token_valid: boolean;     // liveness ping passed
  broker: string;
  login_url: string | null;
  error: string | null;
}

const BROKER_META: Record<string, { label: string; color: string; tokenHint: string; docsUrl: string }> = {
  ZERODHA: {
    label: 'Zerodha (Kite)',
    color: 'text-blue-400',
    tokenHint:
      'After logging in, Zerodha redirects to your callback URL. Copy the access_token from the URL or your Kite developer console.',
    docsUrl: 'https://kite.trade/docs/connect/v3/user/#login-flow',
  },
  INDMONEY: {
    label: 'INDMoney / INDstocks',
    color: 'text-emerald-400',
    tokenHint:
      'Get your access token from the INDstocks developer portal or your broker dashboard and paste it below.',
    docsUrl: 'https://api-docs.indstocks.com/',
  },
};

function Login() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('login');

  // Login step
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  // Broker step
  const [brokerStatus, setBrokerStatus] = useState<BrokerStatus | null>(null);
  const [accessToken, setAccessToken] = useState('');
  const [tokenError, setTokenError] = useState('');
  const [tokenLoading, setTokenLoading] = useState(false);
  const [tokenSaved, setTokenSaved] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    setLoginLoading(true);
    try {
      const response = await authAPI.login(username, password);
      const { access_token } = response.data;
      authTokenStore.set(access_token);

      try {
        const _base = (import.meta as any).env?.VITE_API_BASE || '';
        const r = await fetch(`${_base}/broker/token-status`, {
          headers: { Authorization: `Bearer ${access_token}` },
        });
        if (r.ok) {
          const status: BrokerStatus = await r.json();
          if (!status.has_token) {
            setBrokerStatus(status);
            setStep('broker');
            return;
          }
        }
      } catch {
        // token-status failure must not block login
      }

      navigate('/');
    } catch (err: any) {
      if (err.response?.status === 401) {
        setLoginError('Invalid username or password');
      } else {
        setLoginError(err.response?.data?.detail || 'Login failed. Please try again.');
      }
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSaveToken = async () => {
    if (!accessToken.trim()) {
      setTokenError('Please paste your access token');
      return;
    }
    setTokenError('');
    setTokenLoading(true);
    try {
      const token = authTokenStore.get();
      const _base = (import.meta as any).env?.VITE_API_BASE || '';
      const r = await fetch(`${_base}/broker/set-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ access_token: accessToken.trim() }),
      });
      if (!r.ok) {
        const d = await r.json();
        setTokenError(d.detail || 'Failed to save token');
        return;
      }
      setTokenSaved(true);
      setTimeout(() => navigate('/'), 1200);
    } catch {
      setTokenError('Network error. Please try again.');
    } finally {
      setTokenLoading(false);
    }
  };

  // ── Step 1: Login ──────────────────────────────────────────────────────
  if (step === 'login') {
    return (
      <div className="min-h-screen flex items-center justify-center terminal-shell p-4">
        <div className="w-full max-w-md">
          <div className="panel p-8">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-terminal-green mb-2">FastTrade Terminal</h1>
              <p className="text-slate-400">Sign in to access your trading platform</p>
            </div>

            {loginError && (
              <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/50">
                <p className="text-red-400 text-sm">{loginError}</p>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-6">
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
                  disabled={loginLoading}
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
                  disabled={loginLoading}
                />
              </div>

              <button
                type="submit"
                disabled={loginLoading}
                className="w-full py-3 px-4 bg-terminal-green hover:bg-green-600 text-slate-900
                           font-semibold rounded-lg transition-colors disabled:opacity-50
                           disabled:cursor-not-allowed"
              >
                {loginLoading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <div className="mt-8 text-center text-sm text-slate-500">
              <p>Secured by FastTradeApp Authentication</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Step 2: Broker Token Setup ─────────────────────────────────────────
  const broker = brokerStatus?.broker ?? 'ZERODHA';
  const meta = BROKER_META[broker] ?? BROKER_META['ZERODHA'];

  return (
    <div className="min-h-screen flex items-center justify-center terminal-shell p-4">
      <div className="w-full max-w-lg">
        <div className="panel p-8">

          {/* Header */}
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
              <span className="text-emerald-400 text-sm font-bold">2</span>
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Connect Your Broker</h2>
              <p className="text-xs text-slate-400">
                Step 2 of 2 — Active broker:{' '}
                <span className={`font-semibold ${meta.color}`}>{meta.label}</span>
              </p>
            </div>
          </div>

          {/* Warning */}
          <div className="mt-4 mb-6 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-2">
            <AlertTriangle size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-amber-300">
              {brokerStatus?.token_found && !brokerStatus?.token_valid
                ? <>Existing <span className="font-semibold">{meta.label}</span> token is <span className="font-semibold text-red-300">expired or invalid</span>. Please provide a fresh token to resume live data and schedulers.</>  
                : <>No active <span className="font-semibold">{meta.label}</span> token found. Without it, schedulers, live quotes, and candle backfill will fail on every request.</>
              }
            </p>
          </div>

          {tokenSaved ? (
            <div className="flex flex-col items-center gap-3 py-6">
              <CheckCircle size={40} className="text-emerald-400" />
              <p className="text-emerald-300 font-semibold">Broker token activated!</p>
              <p className="text-xs text-slate-400">Redirecting to dashboard…</p>
            </div>
          ) : (
            <>
              {/* Zerodha: show OAuth login button */}
              {broker === 'ZERODHA' && (
                <div className="mb-5">
                  <p className="text-sm font-medium text-slate-300 mb-2">
                    Step A — Log in to Zerodha and copy your access token
                  </p>
                  {brokerStatus?.login_url ? (
                    <a
                      href={brokerStatus.login_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg
                                 bg-blue-500/20 border border-blue-500/40 text-blue-300
                                 hover:bg-blue-500/30 transition text-sm font-medium"
                    >
                      <ExternalLink size={14} />
                      Open Zerodha Login
                    </a>
                  ) : (
                    <p className="text-xs text-slate-500 italic">
                      ZERODHA_API_KEY not set in .env — configure it and restart the backend.
                    </p>
                  )}
                  <p className="text-xs text-slate-500 mt-2">{meta.tokenHint}</p>
                </div>
              )}

              {/* INDMoney: no OAuth redirect, just paste */}
              {broker === 'INDMONEY' && (
                <div className="mb-5">
                  <p className="text-sm font-medium text-slate-300 mb-1">
                    Get your INDstocks access token
                  </p>
                  <p className="text-xs text-slate-500 mb-2">{meta.tokenHint}</p>
                  <a
                    href={meta.docsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition"
                  >
                    <ExternalLink size={12} />
                    INDstocks API docs
                  </a>
                </div>
              )}

              {/* Paste token — same for both brokers */}
              <div className="mb-5">
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  {broker === 'ZERODHA' ? 'Step B — ' : ''}Paste access token
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      value={accessToken}
                      onChange={(e) => setAccessToken(e.target.value)}
                      placeholder={`Paste ${meta.label} access token…`}
                      className="w-full pl-9 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg
                                 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2
                                 focus:ring-terminal-green focus:border-transparent font-mono"
                    />
                  </div>
                  <button
                    onClick={handleSaveToken}
                    disabled={tokenLoading || !accessToken.trim()}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-terminal-green
                               hover:bg-green-600 text-slate-900 font-semibold text-sm transition
                               disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ArrowRight size={14} />
                    {tokenLoading ? 'Saving…' : 'Activate'}
                  </button>
                </div>
                {tokenError && <p className="text-red-400 text-xs mt-2">{tokenError}</p>}
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3 my-4">
                <div className="flex-1 h-px bg-slate-700/60" />
                <span className="text-xs text-slate-500">or</span>
                <div className="flex-1 h-px bg-slate-700/60" />
              </div>

              {/* Skip */}
              <button
                onClick={() => navigate('/')}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg
                           border border-slate-700/60 text-slate-400 hover:text-slate-200
                           hover:border-slate-500/60 transition text-sm"
              >
                <SkipForward size={14} />
                Skip for now — I'll set it up in Settings
              </button>
              <p className="text-[11px] text-slate-600 text-center mt-2">
                Schedulers and live data will be unavailable until a token is set.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default Login;
