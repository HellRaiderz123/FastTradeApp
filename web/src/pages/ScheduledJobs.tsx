import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  Play,
  RefreshCw,
  Server,
} from 'lucide-react';
import { schedulerAPI, type SchedulerJob } from '../lib/api';
import { useToast } from '../components/Toast';

const formatTimestamp = (value?: string | null) => {
  if (!value) return 'Not scheduled';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

const runStateStyles: Record<string, string> = {
  idle: 'border-slate-700 text-slate-300 bg-slate-900/70',
  running: 'border-cyan-400/40 text-cyan-200 bg-cyan-500/10',
  completed: 'border-emerald-400/40 text-emerald-200 bg-emerald-500/10',
  failed: 'border-rose-400/40 text-rose-200 bg-rose-500/10',
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
  const [runningJobId, setRunningJobId] = useState<string | null>(null);

  const loadJobs = async (background = false) => {
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const response = await schedulerAPI.listJobs();
      const data = response.data;
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
    const timer = window.setInterval(() => loadJobs(true), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const handleRunNow = async (job: SchedulerJob) => {
    setRunningJobId(job.id);
    try {
      await schedulerAPI.runNow(job.id);
      showToast('success', 'Job queued', `${job.label} is running in the background.`);
      await loadJobs(true);
      window.setTimeout(() => loadJobs(true), 1500);
      window.setTimeout(() => loadJobs(true), 5000);
    } catch (err: any) {
      showToast('error', 'Run failed', err?.response?.data?.detail || `Could not run ${job.label}`);
    } finally {
      setRunningJobId(null);
    }
  };

  const counts = useMemo(() => {
    return jobs.reduce(
      (acc, job) => {
        acc[job.category] = (acc[job.category] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [jobs]);

  return (
    <div className="h-full flex flex-col gap-6">
      <div className="terminal-panel rounded-2xl px-6 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Operations</p>
            <h1 className="terminal-title text-3xl text-white">Scheduled Jobs</h1>
            <p className="mt-2 text-sm text-slate-400">
              Inspect every active APScheduler job, see when it runs next, and trigger supported jobs manually.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className={`rounded-xl border px-4 py-2 ${schedulerRunning ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-rose-500/30 bg-rose-500/10 text-rose-200'}`}>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Activity className="w-4 h-4" />
                {schedulerRunning ? 'Scheduler Running' : 'Scheduler Stopped'}
              </div>
              <div className="mt-1 text-xs opacity-80">Timezone: {timezone}</div>
            </div>
            <div className="rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-2 text-slate-200">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Server className="w-4 h-4" />
                {jobCount} Active Jobs
              </div>
              <div className="mt-1 text-xs text-slate-400">Auto-updates every 30 seconds</div>
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

      <div className="terminal-panel rounded-2xl p-0 overflow-hidden flex-1 min-h-0">
        {loading ? (
          <div className="h-full flex items-center justify-center text-slate-400 gap-3">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading jobs...
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
                  <th className="px-5 py-4">Manual Status</th>
                  <th className="px-5 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {jobs.map((job) => {
                  const runStatus = job.manual_run?.status || 'idle';
                  const isRunning = runStatus === 'running' || runningJobId === job.id;
                  return (
                    <tr key={job.id} className="align-top hover:bg-slate-900/40 transition">
                      <td className="px-5 py-4">
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 rounded-lg border border-slate-700 bg-slate-950/60 p-2 text-cyan-300">
                            <Server className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="font-semibold text-white">{job.label}</div>
                            <div className="mt-1 text-xs text-slate-500">{job.id}</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <span className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-300">{job.category}</span>
                              {job.pending && (
                                <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-200">Pending</span>
                              )}
                              {job.coalesce !== null && job.coalesce !== undefined && (
                                <span className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-400">Coalesce: {job.coalesce ? 'On' : 'Off'}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-slate-300">
                        <div className="max-w-md leading-6">{job.trigger}</div>
                        <div className="mt-2 text-xs text-slate-500">Max instances: {job.max_instances ?? '—'}</div>
                      </td>
                      <td className="px-5 py-4 text-slate-300">
                        <div className="flex items-center gap-2 text-sm text-white">
                          <Clock3 className="w-4 h-4 text-slate-500" />
                          {formatTimestamp(job.next_run_time)}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-semibold ${runStateStyles[runStatus] || runStateStyles.idle}`}>
                          {runStatus === 'completed' ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
                          {runStatus === 'failed' ? <AlertTriangle className="w-3.5 h-3.5" /> : null}
                          {runStatus === 'running' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                          {runStatus.toUpperCase()}
                        </span>
                        <div className="mt-2 text-xs text-slate-400">
                          Started: {formatTimestamp(job.manual_run?.started_at)}
                        </div>
                        {job.manual_run?.finished_at && (
                          <div className="mt-1 text-xs text-slate-500">
                            Finished: {formatTimestamp(job.manual_run.finished_at)}
                          </div>
                        )}
                        {job.manual_run?.last_error && (
                          <div className="mt-2 max-w-sm text-xs text-rose-300">{job.manual_run.last_error}</div>
                        )}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button
                          onClick={() => handleRunNow(job)}
                          disabled={!job.manual_run_allowed || isRunning}
                          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition ${job.manual_run_allowed ? 'border border-emerald-400/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20' : 'border border-slate-700 bg-slate-900/60 text-slate-500 cursor-not-allowed'} disabled:opacity-60`}
                        >
                          {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                          {job.manual_run_allowed ? (isRunning ? 'Running...' : 'Run Now') : 'Startup Only'}
                        </button>
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