export interface Metrics {
  total_failed: number;
  total_recovered: number;
  total_abandoned: number;
  total_retry_scheduled: number;
  recovery_rate_percent: number;
  failed_amount_cents: number;
  recovered_amount_cents: number;
  recovered_amount_dollars: number;
  revenue_at_risk_dollars: number;
}

export interface Payment {
  id: number;
  stripe_payment_intent_id: string;
  customer_email: string;
  amount_cents: number;
  amount_dollars: number;
  currency: string;
  status: string;
  decline_code: string | null;
  decline_category: string | null;
  retry_count: number;
  next_retry_at: string | null;
  recovered_at: string | null;
  created_at: string;
}

export interface DeclineCode {
  type: string;
  should_retry: boolean;
  max_retries: number;
  intervals_hours: number[];
  reason: string;
}

const API = "/api";

export async function fetchMetrics(): Promise<Metrics> {
  const res = await fetch(`${API}/metrics`);
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchPayments(status?: string): Promise<Payment[]> {
  const url = status ? `${API}/payments?status=${status}` : `${API}/payments`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch payments");
  return res.json();
}

export async function simulateFailure(
  declineCode: string,
  amountCents: number
): Promise<{ message: string; payment_id: number }> {
  const res = await fetch(`${API}/simulate/failure`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decline_code: declineCode, amount_cents: amountCents }),
  });
  if (!res.ok) throw new Error("Simulation failed");
  return res.json();
}

export async function triggerRetry(
  paymentId: number,
  success: boolean
): Promise<Payment> {
  const res = await fetch(
    `${API}/payments/${paymentId}/retry?success=${success}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("Retry failed");
  return res.json();
}

export async function fetchDeclineCodes(): Promise<Record<string, DeclineCode>> {
  const res = await fetch(`${API}/decline-codes`);
  if (!res.ok) throw new Error("Failed to fetch decline codes");
  return res.json();
}

export function formatCurrency(dollars: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(dollars);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
