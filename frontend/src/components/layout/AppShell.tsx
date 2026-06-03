import { NavLink, Outlet } from "react-router-dom";

import { useLocalConfig } from "../../lib/localConfig";

const navigation = [
  { to: "/fleet", label: "Fleet Overview" },
  { to: "/live", label: "Live Monitor" },
  { to: "/alerts", label: "Alerts & Maintenance" },
  { to: "/config", label: "Local Config" }
];

export function AppShell(): JSX.Element {
  const { apiBaseUrl, isUsingDefaults } = useLocalConfig();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__eyebrow">Elevator PDM</span>
          <h1>Operations Console</h1>
          <p>Browser-local connection settings for the monitoring dashboard.</p>
          <div className="sidebar-status">
            <span className="status-pill status-pill--sidebar">
              {isUsingDefaults ? "Default endpoint" : "Custom endpoint"}
            </span>
            <code>{apiBaseUrl}</code>
          </div>
        </div>

        <nav className="nav">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? "nav__link nav__link--active" : "nav__link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
