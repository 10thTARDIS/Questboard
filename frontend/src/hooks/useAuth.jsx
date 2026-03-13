import { createContext, useContext, useEffect, useState } from "react";
import { fetchMe } from "../api/auth.js";

const AuthContext = createContext(null);

/**
 * Provides authentication state to the entire application.
 * Wraps the root of the component tree (see App.jsx).
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Returns { user, loading, setUser } from the nearest AuthProvider.
 *
 * user    — authenticated User object, or null if not logged in
 * loading — true while the initial /api/me check is in flight
 * setUser — call with null to reflect a logout in UI state
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used inside an <AuthProvider>");
  }
  return ctx;
}
