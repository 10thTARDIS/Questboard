import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth.jsx";
import { ThemeProvider } from "./hooks/useTheme.jsx";
import AuthGuard from "./components/AuthGuard.jsx";
import Login from "./pages/Login.jsx";
import AuthError from "./pages/AuthError.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import CampaignDetail from "./pages/CampaignDetail.jsx";
import SessionDetail from "./pages/SessionDetail.jsx";
import Profile from "./pages/Profile.jsx";
import Admin from "./pages/Admin.jsx";
import CampaignNotes from "./pages/CampaignNotes.jsx";
import CampaignAnalytics from "./pages/CampaignAnalytics.jsx";
import CampaignLore from "./pages/CampaignLore.jsx";

export default function App() {
  return (
    <ThemeProvider>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/auth-error" element={<AuthError />} />

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

          <Route
            path="/profile"
            element={
              <AuthGuard>
                <Profile />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns/:id/notes"
            element={
              <AuthGuard>
                <CampaignNotes />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns/:id/analytics"
            element={
              <AuthGuard>
                <CampaignAnalytics />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns/:id/lore"
            element={
              <AuthGuard>
                <CampaignLore />
              </AuthGuard>
            }
          />
          <Route
            path="/admin"
            element={
              <AuthGuard>
                <Admin />
              </AuthGuard>
            }
          />

          {/* Catch-all: send authenticated users to dashboard, others to login */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
    </ThemeProvider>
  );
}
