import { useEffect, useState } from "react";
import { fetchWorkspace, updateWorkspace, Workspace } from "../api";
import { Toast } from "../components/ui";

export default function SettingsPage() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchWorkspace().then(setWorkspace).catch(() => {});
  }, []);

  const notify = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const toggleDunning = async () => {
    if (!workspace) return;
    const updated = await updateWorkspace({
      dunning_emails_enabled: !workspace.dunning_emails_enabled,
    });
    setWorkspace(updated);
    notify(updated.dunning_emails_enabled ? "Dunning emails enabled" : "Dunning emails disabled");
  };

  const copyApiKey = () => {
    if (!workspace) return;
    navigator.clipboard.writeText(workspace.api_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!workspace) return <div className="loading">Loading settings…</div>;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Workspace configuration and integrations</p>
        </div>
      </header>

      <section className="panel settings-section">
        <h2>Workspace</h2>
        <dl className="settings-dl">
          <dt>Company</dt>
          <dd>{workspace.name}</dd>
          <dt>Plan</dt>
          <dd className="capitalize">{workspace.plan}</dd>
          <dt>Workspace ID</dt>
          <dd className="mono">{workspace.slug}</dd>
        </dl>
      </section>

      <section className="panel settings-section">
        <h2>Stripe integration</h2>
        <div className="integration-row">
          <div>
            <strong>Stripe Billing</strong>
            <p className="muted">
              {workspace.stripe_connected
                ? `Connected · ${workspace.stripe_account_id}`
                : "Not connected"}
            </p>
          </div>
          <span className={`integration-badge ${workspace.stripe_connected ? "on" : "off"}`}>
            {workspace.stripe_connected ? "Active" : "Inactive"}
          </span>
        </div>
        <p className="settings-note">
          Webhook endpoint: <code>POST /webhooks/stripe</code>
        </p>
      </section>

      <section className="panel settings-section">
        <h2>Razorpay (India · UPI AutoPay)</h2>
        <div className="integration-row">
          <div>
            <strong>UPI subscription debits</strong>
            <p className="muted">
              {workspace.razorpay_connected
                ? "Connected · UPI AutoPay webhooks active"
                : "Connect for UPI mandate failure recovery"}
            </p>
          </div>
          <span className={`integration-badge ${workspace.razorpay_connected ? "on" : "off"}`}>
            {workspace.razorpay_connected ? "Active" : "Inactive"}
          </span>
        </div>
        <p className="settings-note">
          Webhook endpoint: <code>POST /webhooks/razorpay</code>
        </p>
      </section>

      <section className="panel settings-section">
        <h2>Dunning — SMS (India)</h2>
        <div className="toggle-row">
          <div>
            <strong>Send UPI failure SMS</strong>
            <p className="muted">
              SMS/WhatsApp nudge when UPI AutoPay fails — primary channel in India.
            </p>
          </div>
          <button
            className={`toggle ${workspace.dunning_sms_enabled ? "on" : ""}`}
            onClick={async () => {
              const updated = await updateWorkspace({
                dunning_sms_enabled: !workspace.dunning_sms_enabled,
              });
              setWorkspace(updated);
              notify(updated.dunning_sms_enabled ? "SMS dunning enabled" : "SMS dunning disabled");
            }}
            aria-pressed={workspace.dunning_sms_enabled}
          />
        </div>
      </section>

      <section className="panel settings-section">
        <h2>Dunning — Email</h2>
        <div className="toggle-row">
          <div>
            <strong>Send payment failure emails</strong>
            <p className="muted">
              Notify customers when a charge fails, before the next retry.
            </p>
          </div>
          <button
            className={`toggle ${workspace.dunning_emails_enabled ? "on" : ""}`}
            onClick={toggleDunning}
            aria-pressed={workspace.dunning_emails_enabled}
          />
        </div>
      </section>

      <section className="panel settings-section">
        <h2>API key</h2>
        <p className="muted">Use this key to authenticate Recover API requests.</p>
        <div className="api-key-row">
          <code>{workspace.api_key}</code>
          <button className="btn btn-ghost" onClick={copyApiKey}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </section>

      <Toast message={toast} />
    </div>
  );
}
