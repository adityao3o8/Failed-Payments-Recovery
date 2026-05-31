import { useEffect, useState } from "react";
import { fetchRetryPolicy, RetryPolicy, updateWorkspace } from "../api";
import { CategoryBadge, Toast } from "../components/ui";

const AGGRESSIVENESS = [
  {
    value: "conservative",
    label: "Conservative",
    desc: "Fewer retries, longer intervals. Best for high-value B2B.",
  },
  {
    value: "balanced",
    label: "Balanced",
    desc: "Default strategy tuned for most subscription businesses.",
  },
  {
    value: "aggressive",
    label: "Aggressive",
    desc: "More retries, shorter intervals. Maximizes recovery rate.",
  },
];

interface UpiCode {
  type: string;
  should_retry: boolean;
  max_retries: number;
  intervals_hours: number[];
  reason: string;
  notify_channel: string;
  salary_cycle_retry: boolean;
}

interface UpiFailureCodes {
  salary_cycle_note: string;
  codes: Record<string, UpiCode>;
}

export default function RetryRulesPage() {
  const [policy, setPolicy] = useState<RetryPolicy | null>(null);
  const [upiCodes, setUpiCodes] = useState<UpiFailureCodes | null>(null);
  const [tab, setTab] = useState<"card" | "upi">("upi");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    fetchRetryPolicy().then(setPolicy).catch(() => {});
    fetch("/api/upi/failure-codes")
      .then((r) => r.json())
      .then(setUpiCodes)
      .catch(() => {});
  }, []);

  const setAggressiveness = async (value: string) => {
    await updateWorkspace({ retry_aggressiveness: value });
    setPolicy((p) => (p ? { ...p, aggressiveness: value } : p));
    setToast("Retry strategy updated");
    setTimeout(() => setToast(null), 3000);
  };

  if (!policy) return <div className="loading">Loading retry rules…</div>;

  const rules = tab === "upi" ? upiCodes?.codes : policy.decline_rules;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Retry rules</h1>
          <p>Card declines (Stripe) and UPI failures (Razorpay / NPCI AutoPay)</p>
        </div>
      </header>

      <section className="panel india-callout">
        <strong>🇮🇳 India — UPI AutoPay</strong>
        <p>
          Subscriptions in India run on UPI e-mandates (AutoPay), not cards. Recover
          classifies NPCI failure reasons and retries on salary days (1st, 5th, 10th)
          when balance is insufficient.
        </p>
        {upiCodes && <p className="muted">{upiCodes.salary_cycle_note}</p>}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Recovery strategy</h2>
        </div>
        <div className="strategy-grid">
          {AGGRESSIVENESS.map((s) => (
            <button
              key={s.value}
              className={`strategy-card ${policy.aggressiveness === s.value ? "selected" : ""}`}
              onClick={() => setAggressiveness(s.value)}
            >
              <strong>{s.label}</strong>
              <p>{s.desc}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div className="filter-tabs" style={{ marginBottom: 0 }}>
            <button
              className={tab === "upi" ? "tab active" : "tab"}
              onClick={() => setTab("upi")}
            >
              UPI (India)
            </button>
            <button
              className={tab === "card" ? "tab active" : "tab"}
              onClick={() => setTab("card")}
            >
              Cards (Stripe)
            </button>
          </div>
          <span className="muted">
            {rules ? Object.keys(rules).length : 0} codes
          </span>
        </div>
        <div className="decline-grid">
          {rules &&
            Object.entries(rules).map(([code, info]) => (
              <div key={code} className="decline-item">
                <code>{code}</code>
                <p>{info.reason}</p>
                <div className="decline-meta">
                  <CategoryBadge category={info.type} />
                  {"notify_channel" in info && (
                    <span className="channel-badge">
                      {(info as UpiCode).notify_channel}
                    </span>
                  )}
                  <span>
                    {info.should_retry
                      ? `${info.max_retries} retries · ${info.intervals_hours.join("h → ")}h`
                      : "No retry"}
                  </span>
                </div>
              </div>
            ))}
        </div>
      </section>

      <Toast message={toast} />
    </div>
  );
}
