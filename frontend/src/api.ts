export interface Workspace {
  id: number;
  name: string;
  slug: string;
  plan: string;
  stripe_connected: boolean;
  stripe_account_id: string | null;
  razorpay_connected: boolean;
  dunning_emails_enabled: boolean;
  dunning_sms_enabled: boolean;
  retry_aggressiveness: string;
  api_key: string;
}

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
  mrr_saved_estimate: number;
  dunning_emails_sent: number;
}

export interface ChartPoint {
  date: string;
  recovered_cents: number;
  failed_cents: number;
}

export interface ActivityItem {
  id: number;
  event_type: string;
  title: string;
  detail: string | null;
  payment_id: number | null;
  created_at: string;
}

export interface Payment {
  id: number;
  stripe_payment_intent_id: string;
  customer_email: string;
  customer_name: string | null;
  payment_rail: string;
  amount_cents: number;
  amount_dollars: number;
  currency: string;
  status: string;
  decline_code: string | null;
  decline_category: string | null;
  retry_count: number;
  next_retry_at: string | null;
  recovered_at: string | null;
  dunning_email_sent: boolean;
  created_at: string;
}

export interface DeclineCode {
  type: string;
  should_retry: boolean;
  max_retries: number;
  intervals_hours: number[];
  reason: string;
}

export interface RetryPolicy {
  aggressiveness: string;
  dunning_emails_enabled: boolean;
  decline_rules: Record<string, DeclineCode>;
}

const API = "/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`API error: ${path}`);
  return res.json();
}

export const fetchWorkspace = () => apiFetch<Workspace>("/workspace");
export const fetchMetrics = () => apiFetch<Metrics>("/metrics");
export const fetchChart = () => apiFetch<ChartPoint[]>("/metrics/chart");
export const fetchActivity = () => apiFetch<ActivityItem[]>("/activity");
export const fetchPayments = (status?: string) =>
  apiFetch<Payment[]>(status ? `/payments?status=${status}` : "/payments");
export const fetchRetryPolicy = () => apiFetch<RetryPolicy>("/retry-policy");

export async function updateWorkspace(data: {
  dunning_emails_enabled?: boolean;
  dunning_sms_enabled?: boolean;
  retry_aggressiveness?: string;
}): Promise<Workspace> {
  return apiFetch<Workspace>("/workspace", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function simulateFailure(
  declineCode: string,
  amountCents: number,
  email?: string
): Promise<{ message: string; payment_id: number }> {
  return apiFetch("/simulate/failure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decline_code: declineCode,
      amount_cents: amountCents,
      email: email ?? `demo+${Date.now()}@example.com`,
    }),
  });
}

export async function triggerRetry(
  paymentId: number,
  success: boolean
): Promise<Payment> {
  return apiFetch(`/payments/${paymentId}/retry?success=${success}`, {
    method: "POST",
  });
}

export function formatCurrency(dollars: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(dollars);
}

export function formatCents(cents: number): string {
  return formatCurrency(cents / 100);
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

export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
