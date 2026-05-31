import { useCallback, useEffect, useState } from "react";
import {
  fetchPayments,
  formatCurrency,
  formatDate,
  Payment,
  simulateFailure,
  triggerRetry,
} from "../api";
import { CategoryBadge, StatusBadge, Toast } from "../components/ui";

const FILTERS = [
  { value: "", label: "All" },
  { value: "retry_scheduled", label: "Scheduled" },
  { value: "recovered", label: "Recovered" },
  { value: "abandoned", label: "Abandoned" },
];

export default function RecoveriesPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [filter, setFilter] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const load = useCallback(async () => {
    const data = await fetchPayments(filter || undefined);
    setPayments(data);
  }, [filter]);

  useEffect(() => {
    load().catch(() => showToast("Failed to load recoveries"));
  }, [load]);

  const handleRetry = async (id: number, success: boolean) => {
    try {
      await triggerRetry(id, success);
      showToast(success ? "Payment recovered" : "Retry failed — rescheduled");
      await load();
    } catch {
      showToast("Action failed");
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Recoveries</h1>
          <p>All failed payments and their recovery status</p>
        </div>
      </header>

      <div className="filter-tabs">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className={filter === f.value ? "tab active" : "tab"}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>Rail</th>
              <th>Customer</th>
              <th>Amount</th>
              <th>Decline reason</th>
              <th>Category</th>
              <th>Status</th>
              <th>Dunning</th>
              <th>Next retry</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {payments.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-cell">
                  No payments match this filter.
                </td>
              </tr>
            ) : (
              payments.map((p) => (
                <tr key={p.id}>
                  <td>
                    <span className={`rail-badge ${p.payment_rail}`}>
                      {p.payment_rail === "upi" ? "UPI" : "Card"}
                    </span>
                  </td>
                  <td>
                    <div className="customer-cell">
                      <strong>{p.customer_name ?? p.customer_email.split("@")[0]}</strong>
                      <span>{p.customer_email}</span>
                    </div>
                  </td>
                  <td className="mono">
                    {p.currency === "inr"
                      ? `₹${(p.amount_dollars).toLocaleString("en-IN")}`
                      : formatCurrency(p.amount_dollars)}
                  </td>
                  <td className="mono">{p.decline_code ?? "—"}</td>
                  <td>
                    <CategoryBadge category={p.decline_category} />
                  </td>
                  <td>
                    <StatusBadge status={p.status} />
                  </td>
                  <td>{p.dunning_email_sent ? "Sent" : "—"}</td>
                  <td className="mono">{formatDate(p.next_retry_at)}</td>
                  <td>
                    {(p.status === "retry_scheduled" || p.status === "failed") && (
                      <div className="actions">
                        <button
                          className="btn btn-sm success"
                          onClick={() => handleRetry(p.id, true)}
                        >
                          Mark recovered
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <details className="dev-panel">
        <summary>Test a failed payment</summary>
        <TestFailureForm onDone={() => { load(); showToast("Test payment created"); }} />
      </details>

      <Toast message={toast} />
    </div>
  );
}

function TestFailureForm({ onDone }: { onDone: () => void }) {
  const [decline, setDecline] = useState("insufficient_funds");
  const [amount, setAmount] = useState(2999);

  return (
    <div className="test-form">
      <select value={decline} onChange={(e) => setDecline(e.target.value)}>
        <option value="insufficient_funds">insufficient_funds</option>
        <option value="expired_card">expired_card</option>
        <option value="stolen_card">stolen_card</option>
        <option value="try_again_later">try_again_later</option>
        <option value="insufficient_balance">insufficient_balance (UPI)</option>
        <option value="upi_autopay_mandate_paused">mandate_paused (UPI)</option>
        <option value="transaction_timeout">transaction_timeout (UPI)</option>
      </select>
      <input
        type="number"
        value={amount}
        onChange={(e) => setAmount(Number(e.target.value))}
        placeholder="Amount (cents)"
      />
      <button
        className="btn btn-primary"
        onClick={() => simulateFailure(decline, amount).then(onDone)}
      >
        Simulate failure
      </button>
    </div>
  );
}
