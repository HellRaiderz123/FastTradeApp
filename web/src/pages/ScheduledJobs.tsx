import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Server,
  Square,
} from 'lucide-react';
import { schedulerAPI, type SchedulerJob } from '../lib/api';
import { useToast } from '../components/Toast';

const formatTimestamp = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
};

// ── Status badge styles ────────────────────────────────────────────────────
const runStateStyles: Record<string, string> = {
  idle:      'border-slate-700 text-slate-400 bg-slate-900/70',
  running:   'border-cyan-400/50 text-cyan-200 bg-cyan-500/15 animate-pulse',
  completed: 'border-emerald-400/40 text-emerald-200 bg-emerald-500/10',
  failed:    'border-rose-400/40 text-rose-200 bg-rose-500/10',
};

const ScheduledJobs: React.FC = () => {
  const { showToast } = useToast();
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [schedulerRunning, setSchedulerRunning] = useState(false);
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [jobCount, setJobCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Track in-flight button actions per job
  const [actionInFlight, setActionInFlight] = useState<Record<string, string>>({});

  const loadJobs = async (background = false) => {
    background ? setRefreshing(true) : setLoading(true);
    try {
      const { data } = await schedulerAPI.listJobs();
      setJobs(data.jobs || []);
      setSchedulerRunning(Boolean(data.scheduler_running));
      setTimezone(data.timezone || 'Asia/Kolkata');
      setJobCount(Number(data.job_count || 0));
      setError(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load scheduled jobs');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadJobs();
    const timer = window.setInterval(() => loadJobs(true), 10000); // poll every 10s
    return () => window.clearInterval(timer);
  }, []);

  const setAction = (jobId: string, action: string) =>
    setActionInFlight((prev) => ({ ...prev, [jobId]: action }));
  const clearAction = (jobId: string) =>
    setActionInFlight((prev) => { const n = { ...prev }; delete n[jobId]; return n; });

  const handleRunNow = async (job: SchedulerJob) => {
    setAction(job.id, 'run');
    try {
      await schedulerAPI.runNow(job.id);
      showToast('success', 'Adhoc run started', `${job.label} is running in the background.`);
      // Poll quickly to reflect running state
      setTimeout(() => loadJobs(true), 800);
      setTimeout(() => loadJobs(true), 3000);
      setTimeout(() => loadJobs(true), 8000);
    } catch (err: any) {
      showToast('error', 'Run failed', err?.response?.data?.detail || `Could not run ${job.label}`);
    } finally {
      clearAction(job.id);
    }
  };

  const handleStop = async (job: SchedulerJob) => {
    setAction(job.id, 'stop');
    try {
      await schedulerAPI.pause(job.id);
      showToast('success', 'Job stopped', `${job.label} will not fire on schedule until resumed.`);
      await loadJobs(true);
    } catch (err: any) {
      showToast('error', 'Stop failed', err?.response?.data?.detail || `Could not stop ${job.label}`);
    } finally {
      clearAction(job.id);
    }
  };

  const handleResume = async (job: SchedulerJob) => {
    setAction(job.id, 'resume');
    try {
      await schedulerAPI.resume(job.id);
      showToast('success', 'Job resumed', `${job.label} is back on its cron schedule.`);
      await loadJobs(true);
    } catch (err: any) {
      showToast('error', 'Resume failed', err?.response?.data?.detail || `Could not resume ${job.label}`);
    } finally {
      clearAction(job.id);
    }
  };

  const counts = useMemo(() =>
    jobs.reduce((acc, job) => { acc[job.category] = (acc[job.category] || 0) + 1; return acc; }, {} as Record<string, number>),
    [jobs]
  );

  const pausedCount = jobs.filter((j) => j.paused).length;
  const runningCount = jobs.filter((j) => j.manual_run?.status === 'running').length;

  return (
    <div className="h-full flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="terminal-panel rounded-2xl px-6 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Operations</p>
            <h1 className="terminal-title text-3xl text-white">Scheduled Jobs</h1>
            <p className="mt-2 text-sm text-slate-400">
              View, run adhoc, stop, or resume any APScheduler job. Stop pauses the cron schedule; Resume restores it.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Scheduler status */}
            <div className={`rounded-xl border px-4 py-2 ${schedulerRunning ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-rose-500/30 bg-rose-500/10 text-rose-200'}`}>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Activity className="w-4 h-4" />
                {schedulerRunning ? 'Scheduler Running' : 'Scheduler Stopped'}
              </div>
              <div className="mt-1 text-xs opacity-70">{timezone}</div>
            </div>

            {/* Counts */}
            <div className="rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-2 text-slate-200">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Server className="w-4 h-4" />
                {jobCount} Jobs
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {runningCount > 0 && <span className="text-cyan-300">{runningCount} running · </span>}
                {pausedCount > 0 && <span className="text-amber-300">{pausedCount} stopped · </span>}
                {jobCount - pausedCount - runningCount} scheduled
              </div>
            </div>

            <button
              onClick={() => loadJobs(true)}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2.5 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-60"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Category pills */}
        <div className="mt-5 flex flex-wrap gap-2">
          {Object.entries(counts).map(([category, count]) => (
            <span key={category} className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs text-slate-300">
              {category}: {count}
            </span>
          ))}
        </div>
      </div>

      {error && (
        <div className="terminal-panel rounded-2xl border border-rose-500/30 bg-rose-500/5 p-5">
          <div className="flex items-center gap-3 text-rose-200">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-semibold">Failed to load scheduled jobs</span>
          </div>
          <p className="mt-2 text-sm text-rose-100/80">{error}</p>
        </div>
      )}

      {/* ── Table ── */}
      <div className="terminal-panel rounded-2xl p-0 overflow-hidden flex-1 min-h-0">
        {loading ? (
          <div className="h-full flex items-center justify-center text-slate-400 gap-3">
            <Loader2 className="w-5 h-5 animate-spin" /> Loading jobs...
          </div>
        ) : jobs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-400 px-6 text-center">
            No scheduler jobs are currently registered.
          </div>
        ) : (
          <div className="overflow-auto h-full">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead className="bg-slate-950/80 sticky top-0 z-10">
                <tr className="text-left text-slate-400 uppercase tracking-[0.16em] text-xs">
                  <th className="px-5 py-4">Job</th>
                  <th className="px-5 py-4">Schedule</th>
                  <th className="px-5 py-4">Next Run</th>
                  <th className="px-5 py-4">Last Adhoc Run</th>
                  <th className="px-5 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {jobs.map((job) => {
                  const runStatus = job.manual_run?.status || 'idle';
                  const isRunning = runStatus === 'running';
                  const isPaused = job.paused;
                  const inFlight = actionInFlight[job.id];

                  return (
                    <tr key={job.id} className={`align-top transition ${isPaused ? 'opacity-60 bg-amber-500/5' : 'hover:bg-slate-900/40'}`}>
                      {/* Job name */}
                      <td className="px-5 py-4">
                        <div className="flex items-start gap-3">
                          <div className={`mt-0.5 rounded-lg border p-2 ${isPaused ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' : isRunning ? 'border-cyan-400/30 text-cyan-300 bg-cyan-500/10' : 'border-slate-700 text-cyan-300 bg-slate-950/60'}`}>
                            {isPaused ? <Pause className="w-4 h-4" /> : isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Server className="w-4 h-4" />}
                          </div>
                          <div>
                            <div className="font-semibold text-white">{job.label}</div>
                            <div className="mt-1 text-xs text-slate-500">{job.id}</div>
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">{job.category}</span>
                              {isPaused && (
                                <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">Stopped</span>
                              )}
                              {isRunning && (
                                <span className="rounded-full border border-cyan-400/40 bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-200 animate-pulse">Running</span>
                              )}
                              {job.pending && (
                                <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-200">Pending</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Schedule */}
                      <td className="px-5 py-4 text-slate-300">
                        <div className="max-w-xs leading-6 text-xs font-mono">{job.trigger}</div>
                        <div className="mt-1 text-xs text-slate-500">Max instances: {job.max_instances ?? '—'}</div>
                      </td>

                      {/* Next run */}
                      <td className="px-5 py-4">
                        {isPaused ? (
                          <span className="text-amber-400 text-xs font-semibold">Paused — not scheduled</span>
                        ) : (
                          <div className="flex items-center gap-2 text-sm text-white">
                            <Clock3 className="w-4 h-4 text-slate-500" />
                            {formatTimestamp(job.next_run_time)}
                          </div>
                        )}
                      </td>

                      {/* Manual run status */}
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${runStateStyles[runStatus] || runStateStyles.idle}`}>
                          {runStatus === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
                          {runStatus === 'failed'    && <AlertTriangle className="w-3.5 h-3.5" />}
                          {runStatus === 'running'   && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                          {runStatus.toUpperCase()}
                        </span>
                        {job.manual_run?.started_at && (
                          <div className="mt-1.5 text-xs text-slate-400">Started: {formatTimestamp(job.manual_run.started_at)}</div>
                        )}
                        {job.manual_run?.finished_at && (
                          <div className="mt-0.5 text-xs text-slate-500">Finished: {formatTimestamp(job.manual_run.finished_at)}</div>
                        )}
                        {job.manual_run?.last_error && (
                          <div className="mt-1.5 max-w-xs text-xs text-rose-300 break-words">{job.manual_run.last_error}</div>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4">
                        <div className="flex items-center justify-end gap-2 flex-wrap">
                          {/* Adhoc Run — always available unless already running */}
                          {job.manual_run_allowed && (
                            <button
                              onClick={() => handleRunNow(job)}
                              disabled={isRunning || !!inFlight}
                              title="Run once now (adhoc) — does not affect schedule"
                              className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {inFlight === 'run' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                              {isRunning ? 'Running…' : 'Adhoc Run'}
                            </button>
                          )}

                          {/* Stop (pause cron) */}
                          {!isPaused && (
                            <button
                              onClick={() => handleStop(job)}
                              disabled={!!inFlight}
                              title="Stop — pauses the cron schedule (job won't fire automatically)"
                              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {inFlight === 'stop' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                              Stop
                            </button>
                          )}

                          {/* Resume (restore cron) */}
                          {isPaused && (
                            <button
                              onClick={() => handleResume(job)}
                              disabled={!!inFlight}
                              title="Resume — restores the cron schedule"
                              className="inline-flex items-center gap-1.5 rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {inFlight === 'resume' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                              Resume
                            </button>
                          )}

                          {/* Startup-only label */}
                          {!job.manual_run_allowed && (
                            <span className="text-xs text-slate-500 italic">Startup only</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScheduledJobs;
