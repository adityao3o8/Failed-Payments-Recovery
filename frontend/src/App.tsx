import { useCallback, useEffect, useState } from "react";
import {
  fetchDeclineCodes,
  fetchMetrics,
  fetchPayments,
  formatCurrency,
  formatDate,
  Metrics,
  Payment,
  simulateFailure,
  triggerRetry,
  DeclineCode,
} from "./api";

function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${status}`}>{status.replace("_", " ")}</span>;
}

function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return <span>—</span>;
  return <span className={`badge ${category}`}>{category}</span>;
}

export default function App() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [declineCodes, setDeclineCodes] = useState<Record<string, DeclineCode>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [simDecline, setSimDecline] = useState("insufficient_funds");
  const [simAmount, setSimAmount] = useState(2999);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const load = useCallback(async () => {
    try {
      setError(null);
      const [m, p, d] = await Promise.all([
        fetchMetrics(),
        fetchPayments(),
        fetchDeclineCodes(),
      ]);
      setMetrics(m);
      setPayments(p);
      setDeclineCodes(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const handleSimulate = async () => {
    try {
      const result = await simulateFailure(simDecline, simAmount);
      showToast(result.message);
      await load();
    } catch {
      showToast("Simulation failed — is the backend running?");
    }
  };

  const handleRetry = async (id: number, success: boolean) => {
    try {
      await triggerRetry(id, success);
      showToast(success ? "Payment recovered!" : "Retry failed, rescheduled");
      await load();
    } catch {
      showToast("Retry action failed");
    }
  };

  if (loading) {
    return (
      <div className="app">
        <div className="loading">Loading recovery dashboard…</div>
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <div className="logo">
          <div className="logo-icon">R</div>
          <div>
            <h1>Recover</h1>
            <p>Payment failure recovery engine</p>
          </div>
        </div>
        <button className="refresh-btn" onClick={load}>
          Refresh
        </button>
      </header>

      {error && (
        <div className="error">
          {error} — run <code>uvicorn app.main:app --reload</code> on port 8000
        </div>
      )}

      {metrics && (
        <div className="metrics-grid">
          <div className="metric-card highlight">
            <div className="metric-label">Recovered Revenue</div>
            <div className="metric-value green">
              {formatCurrency(metrics.recovered_amount_dollars)}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Recovery Rate</div>
            <div className="metric-value green">
              {metrics.recovery_rate_percent}%
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Recovered</div>
            <div className="metric-value">{metrics.total_recovered}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Scheduled Retries</div>
            <div className="metric-value amber">
              {metrics.total_retry_scheduled}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Revenue at Risk</div>
            <div className="metric-value amber">
              {formatCurrency(metrics.revenue_at_risk_dollars)}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Abandoned</div>
            <div className="metric-value red">{metrics.total_abandoned}</div>
          </div>
        </div>
      )}

      <section className="section">
        <div className="section-header">
          <h2>Payments</h2>
        </div>
        <div className="panel">
          <div className="simulate-form">
            <select
              value={simDecline}
              onChange={(e) => setSimDecline(e.target.value)}
            >
              {Object.keys(declineCodes).map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={simAmount}
              onChange={(e) => setSimAmount(Number(e.target.value))}
              placeholder="Amount (cents)"
            />
            <button className="btn btn-primary" onClick={handleSimulate}>
              Simulate Failure
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Amount</th>
                <th>Decline</th>
                <th>Category</th>
                <th>Status</th>
                <th>Next Retry</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td>{p.customer_email}</td>
                  <td className="mono">{formatCurrency(p.amount_dollars)}</td>
                  <td className="mono">{p.decline_code ?? "—"}</td>
                  <td>
                    <CategoryBadge category={p.decline_category} />
                  </td>
                  <td>
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="mono">{formatDate(p.next_retry_at)}</td>
                  <td>
                    {(p.status === "retry_scheduled" || p.status === "failed") && (
                      <div className="actions">
                        <button
                          className="btn btn-sm success"
                          onClick={() => handleRetry(p.id, true)}
                        >
                          Recover
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={() => handleRetry(p.id, false)}
                        >
                          Fail Retry
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <div className="section-header">
          <h2>Decline Code Reference</h2>
        </div>
        <div className="panel">
          <div className="decline-grid">
            {Object.entries(declineCodes).map(([code, info]) => (
              <div key={code} className="decline-item">
                <code>{code}</code>
                <p>{info.reason}</p>
                <div className="decline-meta">
                  <CategoryBadge category={info.type} />
                  <span>
                    {info.should_retry
                      ? `retry: ${info.intervals_hours.join("h → ")}h`
                      : "no retry"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
