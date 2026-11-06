import { useCallback, useEffect, useState } from 'react'
import { CheckCircle, Download, Gauge, RefreshCw, XCircle, Zap } from 'lucide-react'
import api from '../lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LatencyLog {
  id: number
  timestamp: string
  order_id: string
  broker: string | null
  symbol: string | null
  order_type: string
  rtt_ms: number
  overhead_ms: number
  total_latency_ms: number
  status: string
  error: string | null
}

interface BrokerStat {
  total_orders: number
  avg_total: number
  p50_total: number
  p99_total: number
  sla_150ms: number
}

interface Stats {
  total_orders: number
  success_rate: number
  failed_orders: number
  avg_total: number
  sla_150ms: number
  broker_stats: Record<string, BrokerStat>
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function speedRating(ms: number): { label: string; color: string; bg: string } {
  if (ms < 150) return { label: 'Excellent', color: 'text-emerald-400', bg: 'bg-emerald-500' }
  if (ms < 250) return { label: 'Good', color: 'text-yellow-400', bg: 'bg-yellow-500' }
  if (ms < 400) return { label: 'Acceptable', color: 'text-orange-400', bg: 'bg-orange-500' }
  return { label: 'Slow', color: 'text-red-400', bg: 'bg-red-500' }
}

function Bar({ pct, cls }: { pct: number; cls: string }) {
  return (
    <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-500 ${cls}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  )
}

function KpiCard({ label, value, sub, icon, color }: {
  label: string; value: string; sub: string; icon: React.ReactNode; color: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
        </div>
        <div className="opacity-20">{icon}</div>
      </div>
    </div>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function DetailModal({ log, onClose }: { log: LatencyLog; onClose: () => void }) {
  const rating = speedRating(log.total_latency_ms)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Order Latency Breakdown</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">✕</button>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ['Order ID', log.order_id],
            ['Broker', log.broker || 'N/A'],
            ['Symbol', log.symbol || 'N/A'],
            ['Type', log.order_type],
            ['Time', log.timestamp],
            ['Performance', <span className={rating.color}>{rating.label}</span>],
          ].map(([k, v]) => (
            <div key={String(k)} className="rounded-lg bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">{k}</p>
              <p className="font-medium mt-0.5">{v}</p>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium">Latency Breakdown</p>

          <div className="rounded-lg bg-muted/40 p-3 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="font-medium">Total Confirmation Time</span>
              <span className="font-bold">{log.total_latency_ms.toFixed(2)} ms</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div className={`h-full rounded-full ${rating.bg}`} style={{ width: `${Math.min((log.total_latency_ms / 500) * 100, 100)}%` }} />
            </div>
          </div>

          <div className="ml-4 space-y-2">
            <div className="rounded-lg bg-muted/20 p-3">
              <div className="flex justify-between text-sm">
                <div>
                  <span className="font-medium">Broker API Call</span>
                  <span className="ml-2 text-xs text-muted-foreground border border-border rounded px-1">HTTP</span>
                  <p className="text-xs text-muted-foreground mt-0.5">Network + broker processing</p>
                </div>
                <span className="font-bold">{log.rtt_ms.toFixed(2)} ms</span>
              </div>
            </div>
            <div className="rounded-lg bg-muted/20 p-3">
              <div className="flex justify-between text-sm">
                <div>
                  <span className="font-medium">Platform Processing</span>
                  <span className="ml-2 text-xs text-muted-foreground border border-border rounded px-1">FastTrade</span>
                  <p className="text-xs text-muted-foreground mt-0.5">Auth, validation, logging</p>
                </div>
                <span className="font-bold">{log.overhead_ms.toFixed(2)} ms</span>
              </div>
            </div>
          </div>

          {log.error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
              <XCircle className="h-4 w-4 shrink-0" />
              {log.error}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SystemMetrics() {
  const [logs, setLogs] = useState<LatencyLog[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [selected, setSelected] = useState<LatencyLog | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [l, s] = await Promise.allSettled([
        api.get('/latency/logs?limit=100'),
        api.get('/latency/stats'),
      ])
      if (l.status === 'fulfilled') setLogs(Array.isArray(l.value.data) ? l.value.data : [])
      if (s.status === 'fulfilled') setStats(s.value.data)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 30_000)
    return () => clearInterval(id)
  }, [fetchData])

  const handleRefresh = async () => { setRefreshing(true); await fetchData() }
  const handleExport = () => { window.open('/api/latency/export', '_blank') }

  // Distribution buckets
  const total = logs.length || 1
  const dist = {
    excellent: logs.filter(l => l.total_latency_ms < 150).length,
    good: logs.filter(l => l.total_latency_ms >= 150 && l.total_latency_ms < 250).length,
    acceptable: logs.filter(l => l.total_latency_ms >= 250 && l.total_latency_ms < 400).length,
    slow: logs.filter(l => l.total_latency_ms >= 400).length,
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Gauge className="h-5 w-5" /> Order Latency Monitor
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">Track how fast brokers confirm your orders — auto-refreshes every 30s</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90 transition-opacity"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              label="Total Orders Tracked"
              value={String(stats?.total_orders ?? 0)}
              sub="All time"
              icon={<Zap className="h-8 w-8" />}
              color="text-primary"
            />
            <KpiCard
              label="Success Rate"
              value={`${(stats?.success_rate ?? 0).toFixed(1)}%`}
              sub={`${stats?.failed_orders ?? 0} failed`}
              icon={<CheckCircle className="h-8 w-8" />}
              color="text-emerald-400"
            />
            <KpiCard
              label="Avg Confirmation Time"
              value={`${(stats?.avg_total ?? 0).toFixed(2)} ms`}
              sub="End-to-end"
              icon={<Gauge className="h-8 w-8" />}
              color={speedRating(stats?.avg_total ?? 0).color}
            />
            <KpiCard
              label="Fast Orders (<150ms)"
              value={`${(stats?.sla_150ms ?? 0).toFixed(1)}%`}
              sub="Target: 95%"
              icon={<Zap className="h-8 w-8" />}
              color={(stats?.sla_150ms ?? 0) >= 95 ? 'text-emerald-400' : (stats?.sla_150ms ?? 0) >= 85 ? 'text-yellow-400' : 'text-red-400'}
            />
          </div>

          {/* Performance levels legend */}
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm font-medium mb-3">Performance Levels</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Excellent', range: '< 150 ms', bg: 'bg-emerald-500' },
                { label: 'Good', range: '150–250 ms', bg: 'bg-yellow-500' },
                { label: 'Acceptable', range: '250–400 ms', bg: 'bg-orange-500' },
                { label: 'Slow', range: '> 400 ms', bg: 'bg-red-500' },
              ].map(({ label, range, bg }) => (
                <div key={label} className="flex items-center gap-2 text-sm">
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${bg}`} />
                  <span className="font-medium">{label}</span>
                  <span className="text-muted-foreground">{range}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Distribution */}
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm font-medium mb-4">Latency Distribution</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Excellent (<150ms)', count: dist.excellent, bg: 'bg-emerald-500' },
                { label: 'Good (150–250ms)', count: dist.good, bg: 'bg-yellow-500' },
                { label: 'Acceptable (250–400ms)', count: dist.acceptable, bg: 'bg-orange-500' },
                { label: 'Slow (>400ms)', count: dist.slow, bg: 'bg-red-500' },
              ].map(({ label, count, bg }) => (
                <div key={label} className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-semibold">{count}</span>
                  </div>
                  <Bar pct={(count / total) * 100} cls={bg} />
                  <p className="text-xs text-muted-foreground">{((count / total) * 100).toFixed(1)}%</p>
                </div>
              ))}
            </div>
          </div>

          {/* Broker comparison */}
          {stats?.broker_stats && Object.keys(stats.broker_stats).length > 0 && (
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-medium mb-3">Broker Performance Comparison</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground text-xs">
                      <th className="text-left py-2 pr-4">Broker</th>
                      <th className="text-right py-2 pr-4">Avg</th>
                      <th className="text-right py-2 pr-4">P50</th>
                      <th className="text-right py-2 pr-4">P99</th>
                      <th className="text-right py-2 pr-4">Fast %</th>
                      <th className="text-right py-2 pr-4">Orders</th>
                      <th className="py-2">Performance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(stats.broker_stats).map(([broker, d]) => {
                      const r = speedRating(d.avg_total)
                      return (
                        <tr key={broker} className="border-b border-border/50 last:border-0">
                          <td className="py-2 pr-4 font-semibold">{broker}</td>
                          <td className={`py-2 pr-4 text-right font-medium ${r.color}`}>{d.avg_total.toFixed(2)} ms</td>
                          <td className="py-2 pr-4 text-right text-muted-foreground">{d.p50_total.toFixed(2)} ms</td>
                          <td className="py-2 pr-4 text-right text-muted-foreground">{d.p99_total.toFixed(2)} ms</td>
                          <td className="py-2 pr-4 text-right">{d.sla_150ms.toFixed(1)}%</td>
                          <td className="py-2 pr-4 text-right">{d.total_orders}</td>
                          <td className="py-2">
                            <div className="w-24 h-2 rounded-full bg-muted overflow-hidden">
                              <div
                                className={`h-full rounded-full ${r.bg}`}
                                style={{ width: `${Math.max(0, Math.min(100, ((400 - d.avg_total) / 400) * 100))}%` }}
                              />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Recent orders table */}
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm font-medium mb-3">Recent Orders <span className="text-muted-foreground font-normal">({logs.length} tracked)</span></p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-muted-foreground text-xs">
                    <th className="text-left py-2 pr-3">Time</th>
                    <th className="text-left py-2 pr-3">Order ID</th>
                    <th className="text-left py-2 pr-3">Broker</th>
                    <th className="text-left py-2 pr-3">Symbol</th>
                    <th className="text-left py-2 pr-3">Type</th>
                    <th className="text-right py-2 pr-3">Latency</th>
                    <th className="text-left py-2 pr-3">Status</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody>
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-10 text-center text-muted-foreground">
                        No latency data yet — place an order to start tracking
                      </td>
                    </tr>
                  ) : logs.map(log => {
                    const r = speedRating(log.total_latency_ms)
                    return (
                      <tr key={log.id} className="border-b border-border/50 last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="py-2 pr-3 text-muted-foreground whitespace-nowrap">{log.timestamp}</td>
                        <td className="py-2 pr-3 font-mono text-xs">{log.order_id}</td>
                        <td className="py-2 pr-3">{log.broker || 'N/A'}</td>
                        <td className="py-2 pr-3 font-semibold">{log.symbol || 'N/A'}</td>
                        <td className="py-2 pr-3">
                          <span className="rounded border border-border px-1.5 py-0.5 text-xs">{log.order_type}</span>
                        </td>
                        <td className="py-2 pr-3 text-right">
                          <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${r.color} bg-muted`}>
                            {log.total_latency_ms.toFixed(2)} ms
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          {log.status === 'SUCCESS'
                            ? <span className="text-xs font-medium text-emerald-400">SUCCESS</span>
                            : <span className="text-xs font-medium text-red-400">{log.status}</span>}
                        </td>
                        <td className="py-2">
                          <button
                            onClick={() => setSelected(log)}
                            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {selected && <DetailModal log={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
