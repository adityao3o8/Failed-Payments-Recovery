import { useCallback, useEffect, useState } from "react";
import {
  ActivityItem,
  ChartPoint,
  fetchActivity,
  fetchChart,
  fetchMetrics,
  formatCurrency,
  Metrics,
} from "../api";
import { ActivityFeed, MetricCard, RecoveryChart } from "../components/ui";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [chart, setChart] = useState<ChartPoint[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, c, a] = await Promise.all([
        fetchMetrics(),
        fetchChart(),
        fetchActivity(),
      ]);
      setMetrics(m);
      setChart(c);
      setActivity(a);
      setError(null);
    } catch {
      setError("Could not load dashboard — is the backend running on port 8000?");
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Overview</h1>
          <p>Revenue recovery performance for your subscription business</p>
        </div>
        <button className="btn btn-ghost" onClick={load}>
          Refresh
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {metrics && (
        <>
          <div className="metrics-grid">
            <MetricCard
              label="Recovered revenue"
              value={formatCurrency(metrics.recovered_amount_dollars)}
              tone="green"
              sub="Last 30 days"
            />
            <MetricCard
              label="Recovery rate"
              value={`${metrics.recovery_rate_percent}%`}
              tone="green"
            />
            <MetricCard
              label="Revenue at risk"
              value={formatCurrency(metrics.revenue_at_risk_dollars)}
              tone="amber"
              sub={`${metrics.total_retry_scheduled} scheduled retries`}
            />
            <MetricCard
              label="Dunning emails sent"
              value={String(metrics.dunning_emails_sent)}
            />
          </div>

          <div className="two-col">
            <section className="panel">
              <div className="panel-header">
                <h2>Recovery trend</h2>
                <span className="muted">Last 7 days</span>
              </div>
              <RecoveryChart data={chart} />
            </section>

            <section className="panel">
              <div className="panel-header">
                <h2>Recent activity</h2>
              </div>
              <ActivityFeed items={activity} />
            </section>
          </div>

          <section className="panel insight-panel">
            <h2>What Recover is doing</h2>
            <div className="insight-grid">
              <div>
                <span className="insight-num green">{metrics.total_recovered}</span>
                <span>payments recovered</span>
              </div>
              <div>
                <span className="insight-num amber">{metrics.total_retry_scheduled}</span>
                <span>retries in queue</span>
              </div>
              <div>
                <span className="insight-num red">{metrics.total_abandoned}</span>
                <span>abandoned after max retries</span>
              </div>
              <div>
                <span className="insight-num">{formatCurrency(metrics.mrr_saved_estimate)}</span>
                <span>estimated MRR saved</span>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
