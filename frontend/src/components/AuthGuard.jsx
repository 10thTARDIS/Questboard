import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";

/**
 * Wraps any route that requires authentication.
 * Shows a loading state while the session check is in flight,
 * then redirects to /login if the user is not authenticated.
 */
export default function AuthGuard({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-gray-600 dark:text-gray-400">Loading…</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
