export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>{status.replace(/_/g, " ")}</span>
  );
}

export function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return <span className="muted">—</span>;
  return <span className={`badge ${category}`}>{category}</span>;
}

export function MetricCard({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone?: "green" | "amber" | "red";
  sub?: string;
}) {
  return (
    <div className={`metric-card ${tone === "green" ? "highlight" : ""}`}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone ?? ""}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export function RecoveryChart({ data }: { data: { date: string; recovered_cents: number; failed_cents: number }[] }) {
  const max = Math.max(...data.map((d) => d.recovered_cents + d.failed_cents), 1);

  return (
    <div className="chart">
      {data.map((d) => {
        const recoveredH = (d.recovered_cents / max) * 100;
        const failedH = (d.failed_cents / max) * 100;
        return (
          <div key={d.date} className="chart-col">
            <div className="chart-bars">
              <div
                className="chart-bar recovered"
                style={{ height: `${Math.max(recoveredH, 4)}%` }}
                title={`Recovered: $${(d.recovered_cents / 100).toFixed(0)}`}
              />
              <div
                className="chart-bar failed"
                style={{ height: `${Math.max(failedH, 4)}%` }}
                title={`Failed: $${(d.failed_cents / 100).toFixed(0)}`}
              />
            </div>
            <span className="chart-label">{d.date}</span>
          </div>
        );
      })}
      <div className="chart-legend">
        <span><i className="dot recovered" /> Recovered</span>
        <span><i className="dot failed" /> Failed</span>
      </div>
    </div>
  );
}

export function ActivityFeed({
  items,
}: {
  items: { id: number; event_type: string; title: string; detail: string | null; created_at: string }[];
}) {
  if (items.length === 0) {
    return <p className="empty-state">No activity yet.</p>;
  }

  return (
    <ul className="activity-list">
      {items.map((item) => (
        <li key={item.id} className={`activity-item ${item.event_type}`}>
          <div className="activity-dot" />
          <div>
            <strong>{item.title}</strong>
            {item.detail && <p>{item.detail}</p>}
            <time>{new Date(item.created_at).toLocaleString()}</time>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="toast">{message}</div>;
}
