import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { fetchWorkspace, Workspace } from "../api";

const NAV = [
  { to: "/app", label: "Overview", end: true },
  { to: "/app/recoveries", label: "Recoveries" },
  { to: "/app/retry-rules", label: "Retry rules" },
  { to: "/app/settings", label: "Settings" },
];

export default function AppLayout() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchWorkspace().then(setWorkspace).catch(() => {});
  }, []);

  return (
    <div className="product-shell">
      <aside className="sidebar">
        <div className="sidebar-brand" onClick={() => navigate("/")}>
          <div className="logo-icon">R</div>
          <div>
            <strong>Recover</strong>
            <span>Revenue recovery</span>
          </div>
        </div>

        {workspace && (
          <div className="workspace-chip">
            <span className="workspace-name">{workspace.name}</span>
            <span className="plan-badge">{workspace.plan}</span>
          </div>
        )}

        <nav className="sidebar-nav">
          {NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          {workspace?.stripe_connected ? (
            <div className="stripe-status connected">
              <span className="dot" /> Stripe connected
            </div>
          ) : (
            <div className="stripe-status disconnected">
              <span className="dot" /> Connect Stripe
            </div>
          )}
        </div>
      </aside>

      <main className="product-main">
        <Outlet context={{ workspace }} />
      </main>
    </div>
  );
}
