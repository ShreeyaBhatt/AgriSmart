import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell.jsx";
import { ProtectedRoute, useAuth } from "./auth/AuthContext.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ScanFlow from "./pages/ScanFlow.jsx";
import PlotNew from "./pages/PlotNew.jsx";
import PlotDetail from "./pages/PlotDetail.jsx";
import SoilCheck from "./pages/SoilCheck.jsx";
import Weather from "./pages/Weather.jsx";
import Sustainability from "./pages/Sustainability.jsx";
import Assistant from "./pages/Assistant.jsx";
import Settings from "./pages/Settings.jsx";

function Shell({ children }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

export default function App() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />

      <Route path="/" element={<Shell><Dashboard /></Shell>} />
      <Route path="/scan" element={<Shell><ScanFlow /></Shell>} />
      <Route path="/plots/new" element={<Shell><PlotNew /></Shell>} />
      <Route path="/plots/:id" element={<Shell><PlotDetail /></Shell>} />
      <Route path="/soil" element={<Shell><SoilCheck /></Shell>} />
      <Route path="/weather" element={<Shell><Weather /></Shell>} />
      <Route path="/sustainability" element={<Shell><Sustainability /></Shell>} />
      <Route path="/assistant" element={<Shell><Assistant /></Shell>} />
      <Route path="/settings" element={<Shell><Settings /></Shell>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
