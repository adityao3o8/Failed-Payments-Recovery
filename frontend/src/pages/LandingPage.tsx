import { Link } from "react-router-dom";

export default function LandingPage() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="logo">
          <div className="logo-icon">R</div>
          <span>Recover</span>
        </div>
        <div className="landing-nav-links">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <Link to="/app" className="btn btn-primary">
            Open dashboard
          </Link>
        </div>
      </nav>

      <header className="hero">
        <p className="eyebrow">Payment recovery for subscription businesses</p>
        <h1>
          Stop losing revenue to
          <br />
          <span className="gradient-text">failed payments</span>
        </h1>
        <p className="hero-sub">
          Recover automatically retries failed charges, sends smart dunning emails,
          and tracks every dollar saved — built for Stripe billing teams.
        </p>
        <div className="hero-cta">
          <Link to="/app" className="btn btn-primary btn-lg">
            View live dashboard
          </Link>
          <a href="#how" className="btn btn-ghost btn-lg">
            See how it works
          </a>
        </div>
        <div className="hero-stats">
          <div>
            <strong>12.4%</strong>
            <span>avg recovery rate lift</span>
          </div>
          <div>
            <strong>$847</strong>
            <span>saved per 100 failed charges</span>
          </div>
          <div>
            <strong>&lt;5 min</strong>
            <span>Stripe connect time</span>
          </div>
        </div>
      </header>

      <section id="features" className="features">
        <h2>Everything you need to recover revenue</h2>
        <div className="feature-grid">
          <article>
            <h3>Smart retry engine</h3>
            <p>
              Classifies every decline code — hard, soft, retryable — and schedules
              retries at the optimal time. No blind retries on stolen cards.
            </p>
          </article>
          <article>
            <h3>Dunning emails</h3>
            <p>
              Automatically notify customers when a payment fails, before the next
              retry attempt. Reduce involuntary churn without manual ops work.
            </p>
          </article>
          <article>
            <h3>Recovery analytics</h3>
            <p>
              Track recovery rate, revenue saved, and revenue at risk in real time.
              Know exactly what Recover is doing for your MRR.
            </p>
          </article>
          <article>
            <h3>Stripe-native</h3>
            <p>
              Connect your Stripe account, receive webhooks, and start recovering
              failed subscription payments in minutes.
            </p>
          </article>
        </div>
      </section>

      <section id="how" className="how-it-works">
        <h2>How Recover works</h2>
        <ol className="steps">
          <li>
            <span>1</span>
            <div>
              <strong>Payment fails</strong>
              <p>Stripe sends a webhook when a subscription charge declines.</p>
            </div>
          </li>
          <li>
            <span>2</span>
            <div>
              <strong>Decline classified</strong>
              <p>Recover maps the decline code to a retry strategy or blocks retry.</p>
            </div>
          </li>
          <li>
            <span>3</span>
            <div>
              <strong>Customer notified</strong>
              <p>Dunning email sent so customers can update their card.</p>
            </div>
          </li>
          <li>
            <span>4</span>
            <div>
              <strong>Smart retry</strong>
              <p>Charge retried at the optimal time. Revenue recovered.</p>
            </div>
          </li>
        </ol>
      </section>

      <footer className="landing-footer">
        <div className="logo">
          <div className="logo-icon">R</div>
          <span>Recover</span>
        </div>
        <p>Built for fintech · Payment failure recovery engine</p>
      </footer>
    </div>
  );
}
