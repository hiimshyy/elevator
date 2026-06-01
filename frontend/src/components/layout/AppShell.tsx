import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  { to: "/fleet", label: "Fleet Overview" },
  { to: "/live", label: "Live Monitor" },
  { to: "/alerts", label: "Alerts & Maintenance" }
];

export function AppShell(): JSX.Element {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__eyebrow">Elevator PDM</span>
          <h1>Operations Console</h1>
          <p>React migration scaffold for the monitoring dashboard.</p>
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
