import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth.jsx";
import AuthGuard from "./components/AuthGuard.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import CampaignDetail from "./pages/CampaignDetail.jsx";
import SessionDetail from "./pages/SessionDetail.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />

          {/* Protected */}
          <Route
            path="/dashboard"
            element={
              <AuthGuard>
                <Dashboard />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns/:id"
            element={
              <AuthGuard>
                <CampaignDetail />
              </AuthGuard>
            }
          />
          <Route
            path="/sessions/:id"
            element={
              <AuthGuard>
                <SessionDetail />
              </AuthGuard>
            }
          />

          {/* Catch-all: send authenticated users to dashboard, others to login */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
