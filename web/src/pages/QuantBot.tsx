import React, { useState, useEffect, useCallback } from 'react';
import {
  Bot, Search, RefreshCw, Loader2, AlertTriangle, CheckCircle2,
  TrendingUp, TrendingDown, Activity, Target, Shield, Zap,
  BarChart3, Layers, Clock, ChevronRight,
} from 'lucide-react';
import { quantAPI, CashQuantReport, OptionsQuantReport, RiskCheckResult } from '../api/quantAPI';

// ── helpers ──────────────────────────────────────────────────────────────────

const fmt2 = (n: number) => n.toFixed(2);
const fmt0 = (n: number) => n.toFixed(0);
const pct = (n: number) => `${n.toFixed(1)}%`;
const sign = (n: number) => (n >= 0 ? '+' : '') + fmt2(n);

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${color}`}>
      {label}
    </span>
  );
}

function Tile({ label, value, sub, accent }: { label: string; value: React.ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="p-3 bg-slate-700/50 rounded-lg">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-base font-bold ${accent ?? 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 bg-slate-700/40 border-b border-slate-700 flex items-center gap-2">
        <Icon className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-semibold text-white">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

// ── colour helpers ────────────────────────────────────────────────────────────

const regimeColor = (r: string) =>
  r === 'TRENDING' ? 'text-green-400' : r === 'MEAN_REVERTING' ? 'text-amber-400' : 'text-slate-400';

const rvolColor = (s: string) =>
  s === 'HIGH' ? 'text-green-400' : s === 'LOW' ? 'text-red-400' : 'text-slate-400';

const orbColor = (s: string) =>
  s === 'BULLISH' ? 'text-green-400' : s === 'BEARISH' ? 'text-red-400' : 'text-slate-400';

const vwapColor = (s: string) =>
  s === 'ABOVE' ? 'text-green-400' : s === 'BELOW' ? 'text-red-400' : 'text-slate-400';

const ivColor = (ivp: number) =>
  ivp > 65 ? 'text-red-400' : ivp < 35 ? 'text-green-400' : 'text-slate-300';

const gexColor = (g: string) =>
  g === 'POSITIVE_GEX' ? 'text-green-400' : g === 'NEGATIVE_GEX' ? 'text-red-400' : 'text-slate-300';

const pcrColor = (p: number) =>
  p > 1.2 ? 'text-green-400' : p < 0.8 ? 'text-red-400' : 'text-slate-300';

// ── main page ─────────────────────────────────────────────────────────────────

const QuantBot: React.FC = () => {
  const [inputValue, setInputValue] = useState('NIFTY');
  const [symbol, setSymbol] = useState('NIFTY');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cash, setCash] = useState<CashQuantReport | null>(null);
  const [options, setOptions] = useState<OptionsQuantReport | null>(null);
  const [risk, setRisk] = useState<RiskCheckResult | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const runAnalysis = useCallback(async (sym: string) => {
    if (!sym || sym.length < 2) return;
    setLoading(true);
    setError(null);

    try {
      const [cashRes, riskRes] = await Promise.all([
        quantAPI.getCashReport(sym),
        quantAPI.checkRisk(sym, 0, true),
      ]);
      setCash(cashRes.data);
      setRisk(riskRes.data);

      try {
        const optRes = await quantAPI.getOptionsReport(sym);
        setOptions(optRes.data);
      } catch {
        setOptions(null);
      }

      setLastUpdate(new Date());
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Analysis failed');
      setCash(null);
      setOptions(null);
      setRisk(null);
    }

    setLoading(false);
  }, []);

  useEffect(() => { runAnalysis(symbol); }, [symbol]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const s = inputValue.trim().toUpperCase();
    if (s) setSymbol(s);
  };

  return (
    <div className="min-h-screen bg-slate-900 p-6 space-y-6">

      {/* ── Header ── */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Bot className="w-7 h-7 text-purple-400" />
            Quant Bot
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Hedge-fund grade analysis — ORB · RVOL · VWAP · Hurst · Greeks · GEX · IVP · Max Pain · Risk Guard
          </p>
        </div>
        {lastUpdate && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock className="w-3.5 h-3.5" />
            Updated {lastUpdate.toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* ── Search ── */}
      <form onSubmit={handleSubmit} className="flex gap-2 max-w-md">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Symbol — RELIANCE, NIFTY, BANKNIFTY…"
            className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-600 text-white font-medium rounded-lg transition-colors flex items-center gap-2 text-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
          Analyze
        </button>
        <button
          type="button"
          onClick={() => runAnalysis(symbol)}
          disabled={loading}
          className="px-3 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </form>

      {/* ── Error ── */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* ── Risk Guard Banner ── */}
      {risk && (
        <div className={`flex items-center gap-3 p-3 rounded-lg border text-sm ${
          risk.allowed
            ? 'bg-green-500/10 border-green-500/30 text-green-300'
            : 'bg-red-500/10 border-red-500/30 text-red-300'
        }`}>
          {risk.allowed
            ? <CheckCircle2 className="w-4 h-4 shrink-0" />
            : <Shield className="w-4 h-4 shrink-0" />}
          <div className="flex-1">
            <span className="font-semibold">{risk.allowed ? 'Trade Allowed' : 'Trade Blocked'}</span>
            {risk.size_multiplier < 1 && (
              <span className="ml-2 text-amber-400">· Size reduced to {(risk.size_multiplier * 100).toFixed(0)}%</span>
            )}
            {risk.current_vix != null && (
              <span className="ml-2 text-slate-400">· VIX {fmt2(risk.current_vix)}</span>
            )}
          </div>
          {risk.blocks.length > 0 && (
            <span className="text-xs text-red-400">{risk.blocks[0]}</span>
          )}
          {risk.warnings.length > 0 && risk.blocks.length === 0 && (
            <span className="text-xs text-amber-400">{risk.warnings[0]}</span>
          )}
        </div>
      )}

      {cash && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* ── Left column ── */}
          <div className="xl:col-span-2 space-y-6">

            {/* Regime & Momentum */}
            <Section title="Market Regime & Momentum" icon={Activity}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Tile
                  label="Regime"
                  value={cash.regime.replace('_', ' ')}
                  sub={`Hurst = ${cash.hurst_exponent.toFixed(3)}`}
                  accent={regimeColor(cash.regime)}
                />
                <Tile
                  label="RVOL"
                  value={`${fmt2(cash.rvol)}×`}
                  sub={cash.rvol_signal}
                  accent={rvolColor(cash.rvol_signal)}
                />
                <Tile
                  label="Z-Score (20)"
                  value={fmt2(cash.zscore_20)}
                  sub={Math.abs(cash.zscore_20) > 2 ? 'Extreme' : 'Normal'}
                  accent={Math.abs(cash.zscore_20) > 2 ? 'text-amber-400' : 'text-slate-300'}
                />
                <Tile
                  label="BB Width %ile"
                  value={pct(cash.bb_width_percentile)}
                  sub={cash.bb_width_percentile < 20 ? 'Squeeze' : cash.bb_width_percentile > 80 ? 'Expansion' : 'Normal'}
                  accent={cash.bb_width_percentile < 20 ? 'text-amber-400' : 'text-slate-300'}
                />
              </div>
            </Section>

            {/* ORB & VWAP */}
            <Section title="ORB & VWAP Bands" icon={BarChart3}>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <Tile
                  label="ORB Breakout"
                  value={cash.orb_breakout}
                  sub={`H ${fmt2(cash.orb_high)} · L ${fmt2(cash.orb_low)}`}
                  accent={orbColor(cash.orb_breakout)}
                />
                <Tile
                  label="VWAP"
                  value={`₹${fmt2(cash.vwap)}`}
                  sub={cash.price_vs_vwap}
                  accent={vwapColor(cash.price_vs_vwap)}
                />
                <div className="p-3 bg-slate-700/50 rounded-lg col-span-2 sm:col-span-1">
                  <p className="text-xs text-slate-400 mb-2">VWAP Bands</p>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-red-400">+2σ</span>
                      <span className="text-slate-300">₹{fmt2(cash.vwap_upper_2sd)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-amber-400">+1σ</span>
                      <span className="text-slate-300">₹{fmt2(cash.vwap_upper_1sd)}</span>
                    </div>
                    <div className="flex justify-between border-y border-slate-600 py-1">
                      <span className="text-purple-400">VWAP</span>
                      <span className="text-white font-semibold">₹{fmt2(cash.vwap)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-amber-400">-1σ</span>
                      <span className="text-slate-300">₹{fmt2(cash.vwap_lower_1sd)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-400">-2σ</span>
                      <span className="text-slate-300">₹{fmt2(cash.vwap_lower_2sd)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </Section>

            {/* Relative Strength */}
            <Section title="Relative Strength" icon={TrendingUp}>
              <div className="grid grid-cols-2 gap-3">
                <Tile
                  label="RS vs Nifty (5d)"
                  value={`${sign(cash.rs_vs_nifty_5d)}%`}
                  sub="5-day return differential"
                  accent={cash.rs_vs_nifty_5d >= 0 ? 'text-green-400' : 'text-red-400'}
                />
                <Tile
                  label="RS vs Sector (5d)"
                  value={`${sign(cash.rs_vs_sector_5d)}%`}
                  sub="5-day return differential"
                  accent={cash.rs_vs_sector_5d >= 0 ? 'text-green-400' : 'text-red-400'}
                />
              </div>
            </Section>

            {/* Options section */}
            {options && (
              <>
                {/* Greeks */}
                <Section title="ATM Greeks" icon={Layers}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-slate-400 border-b border-slate-700">
                          <th className="text-left pb-2">Side</th>
                          <th className="text-right pb-2">Delta</th>
                          <th className="text-right pb-2">Gamma</th>
                          <th className="text-right pb-2">Theta</th>
                          <th className="text-right pb-2">Vega</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700/50">
                        <tr>
                          <td className="py-2 text-green-400 font-semibold">CE {fmt0(options.atm_strike)}</td>
                          <td className="py-2 text-right text-slate-300">{options.atm_ce_delta.toFixed(4)}</td>
                          <td className="py-2 text-right text-slate-300">{options.atm_ce_gamma.toFixed(6)}</td>
                          <td className="py-2 text-right text-red-400">{options.atm_ce_theta.toFixed(4)}</td>
                          <td className="py-2 text-right text-blue-400">{options.atm_ce_vega.toFixed(4)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-red-400 font-semibold">PE {fmt0(options.atm_strike)}</td>
                          <td className="py-2 text-right text-slate-300">{options.atm_pe_delta.toFixed(4)}</td>
                          <td className="py-2 text-right text-slate-300">{options.atm_pe_gamma.toFixed(6)}</td>
                          <td className="py-2 text-right text-red-400">{options.atm_pe_theta.toFixed(4)}</td>
                          <td className="py-2 text-right text-blue-400">{options.atm_pe_vega.toFixed(4)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <Tile
                      label="ATM IV"
                      value={pct(options.atm_iv * 100)}
                      accent="text-white"
                    />
                    <Tile
                      label="IV Percentile"
                      value={pct(options.iv_percentile)}
                      sub={options.iv_percentile > 65 ? 'Sell premium' : options.iv_percentile < 35 ? 'Buy premium' : 'Neutral'}
                      accent={ivColor(options.iv_percentile)}
                    />
                    <Tile
                      label="IV Rank"
                      value={pct(options.iv_rank)}
                      accent={ivColor(options.iv_rank)}
                    />
                  </div>
                </Section>

                {/* OI Microstructure */}
                <Section title="OI Microstructure" icon={Target}>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <Tile
                      label="PCR (OI)"
                      value={fmt2(options.pcr_oi)}
                      sub={options.pcr_oi > 1.2 ? 'Bullish' : options.pcr_oi < 0.8 ? 'Bearish' : 'Neutral'}
                      accent={pcrColor(options.pcr_oi)}
                    />
                    <Tile
                      label="PCR (Chg OI)"
                      value={fmt2(options.pcr_change_oi)}
                      accent={pcrColor(options.pcr_change_oi)}
                    />
                    <Tile
                      label="Max Pain"
                      value={fmt0(options.max_pain)}
                      sub="Expiry magnet"
                      accent="text-amber-400"
                    />
                    <Tile
                      label="ATM Strike"
                      value={fmt0(options.atm_strike)}
                      sub={`Spot ₹${fmt2(options.spot)}`}
                      accent="text-white"
                    />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <p className="text-xs text-red-400 mb-1">Call Wall (Resistance)</p>
                      <p className="text-lg font-bold text-red-300">{fmt0(options.call_wall)}</p>
                      <p className="text-xs text-slate-500">Highest CE OI strike</p>
                    </div>
                    <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                      <p className="text-xs text-green-400 mb-1">Put Wall (Support)</p>
                      <p className="text-lg font-bold text-green-300">{fmt0(options.put_wall)}</p>
                      <p className="text-xs text-slate-500">Highest PE OI strike</p>
                    </div>
                  </div>
                </Section>

                {/* GEX */}
                <Section title="Gamma Exposure (GEX)" icon={Zap}>
                  <div className="grid grid-cols-2 gap-3">
                    <Tile
                      label="Net GEX"
                      value={`${options.net_gex.toFixed(2)}B`}
                      sub={options.gex_regime === 'POSITIVE_GEX' ? 'Mean-reverting' : options.gex_regime === 'NEGATIVE_GEX' ? 'Trending / volatile' : 'Neutral'}
                      accent={gexColor(options.gex_regime)}
                    />
                    <Tile
                      label="GEX Regime"
                      value={options.gex_regime.replace(/_/g, ' ')}
                      sub={options.gex_regime === 'POSITIVE_GEX' ? 'Dealers sell rallies, buy dips' : options.gex_regime === 'NEGATIVE_GEX' ? 'Dealers amplify moves' : ''}
                      accent={gexColor(options.gex_regime)}
                    />
                  </div>
                </Section>
              </>
            )}
          </div>

          {/* ── Right column ── */}
          <div className="space-y-6">

            {/* ATR & Position Sizing */}
            <Section title="ATR & Position Sizing" icon={Shield}>
              <div className="space-y-3">
                <Tile label="ATR (14)" value={`₹${fmt2(cash.atr_14)}`} sub="Average True Range" />
                <Tile
                  label="Suggested Stop Loss"
                  value={`₹${fmt2(cash.suggested_stop_loss)}`}
                  sub="1.5× ATR below price"
                  accent="text-red-400"
                />
                <Tile
                  label="Position Size"
                  value={`${cash.position_size_lots} lots`}
                  sub="Based on 1% account risk"
                  accent="text-purple-400"
                />
              </div>
            </Section>

            {/* Delivery & Institutional */}
            {cash.delivery_pct > 0 && (
              <Section title="Delivery & Institutional" icon={TrendingUp}>
                <div className={`p-3 rounded-lg ${cash.institutional_accumulation ? 'bg-green-500/10 border border-green-500/30' : 'bg-slate-700/50'}`}>
                  <p className="text-xs text-slate-400 mb-1">Delivery %</p>
                  <p className={`text-2xl font-bold ${cash.delivery_pct > 60 ? 'text-green-400' : 'text-slate-300'}`}>
                    {pct(cash.delivery_pct)}
                  </p>
                  {cash.institutional_accumulation && (
                    <div className="flex items-center gap-1.5 mt-2 text-green-400 text-xs font-semibold">
                      <Zap className="w-3.5 h-3.5" />
                      Institutional Accumulation Signal
                    </div>
                  )}
                </div>
              </Section>
            )}

            {/* Structure Recommendation */}
            {options && options.recommended_structure !== 'NONE' && (
              <Section title="Structure Recommendation" icon={Bot}>
                <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                  <p className="text-xs text-purple-400 mb-1">Recommended</p>
                  <p className="text-lg font-bold text-purple-300">
                    {options.recommended_structure.replace(/_/g, ' ')}
                  </p>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    {options.structure_rationale}
                  </p>
                </div>
              </Section>
            )}

            {/* Risk Check Detail */}
            {risk && (
              <Section title="Risk Guard Detail" icon={Shield}>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Trade Allowed</span>
                    {risk.allowed
                      ? <Badge label="YES" color="bg-green-500/20 text-green-400" />
                      : <Badge label="BLOCKED" color="bg-red-500/20 text-red-400" />}
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Size Multiplier</span>
                    <span className={`font-semibold ${risk.size_multiplier < 1 ? 'text-amber-400' : 'text-green-400'}`}>
                      {(risk.size_multiplier * 100).toFixed(0)}%
                    </span>
                  </div>
                  {risk.current_vix != null && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">India VIX</span>
                      <span className={`font-semibold ${risk.current_vix > 20 ? 'text-red-400' : 'text-slate-300'}`}>
                        {fmt2(risk.current_vix)}
                      </span>
                    </div>
                  )}
                  {risk.warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-400">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      {w}
                    </div>
                  ))}
                  {risk.blocks.map((b, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
                      <Shield className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      {b}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* No options data notice */}
            {!options && !loading && (
              <div className="p-3 bg-slate-800 border border-slate-700 rounded-xl text-xs text-slate-500 flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                Options data unavailable for {symbol}. Ensure broker is connected and symbol has F&O contracts.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!cash && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <Bot className="w-12 h-12 mb-4 text-slate-700" />
          <p>Enter a symbol and click Analyze to run the quant engine.</p>
        </div>
      )}
    </div>
  );
};

export default QuantBot;
