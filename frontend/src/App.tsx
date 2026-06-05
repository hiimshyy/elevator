import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { AlertsMaintenancePage } from "./pages/AlertsMaintenancePage";
// import { ConfigPage } from "./pages/ConfigPage";
import { FleetOverviewPage } from "./pages/FleetOverviewPage";
import { LiveMonitorPage } from "./pages/LiveMonitorPage";

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/fleet" replace />} />
        <Route path="/fleet" element={<FleetOverviewPage />} />
        <Route path="/live" element={<LiveMonitorPage />} />
        <Route path="/alerts" element={<AlertsMaintenancePage />} />
        {/* <Route path="/config" element={<ConfigPage />} /> */}
      </Route>
    </Routes>
  );
}
