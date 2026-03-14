/**
 * Admin — site administration panel.
 *
 * Lists all registered users with last-login dates and lets admins
 * grant or revoke admin status.  Only accessible to users with is_admin=true.
 */

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import { fetchAdminUsers, setAdminStatus } from "../api/auth.js";

function fmt(iso) {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function Admin() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Redirect non-admins
  useEffect(() => {
    if (user && !user.is_admin) navigate("/dashboard", { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    fetchAdminUsers()
      .then(setUsers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleToggleAdmin = async (target) => {
    const newValue = !target.is_admin;
    const verb = newValue ? "grant admin to" : "revoke admin from";
    if (!confirm(`${verb} ${target.effective_display_name}?`)) return;
    setActionError(null);
    try {
      const updated = await setAdminStatus(target.id, newValue);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e) {
      setActionError(e.message);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link to="/dashboard" className="text-gray-500 hover:text-white transition text-sm">
          ← Dashboard
        </Link>
        <span className="text-gray-700">/</span>
        <span className="font-semibold">Admin</span>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        <h2 className="text-lg font-bold mb-6">Users</h2>

        {actionError && (
          <p className="mb-4 rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
            {actionError}
          </p>
        )}

        {loading && <p className="text-gray-500 text-sm">Loading users…</p>}
        {error && <p className="text-red-400 text-sm">{error}</p>}

        {!loading && !error && (
          <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-400 text-xs">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Last login</th>
                  <th className="px-4 py-3 font-medium">Joined</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-3">
                      <div className="font-medium">{u.effective_display_name}</div>
                      {u.display_name_override && (
                        <div className="text-xs text-gray-500">{u.display_name}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-400">{u.email ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-400">{fmt(u.last_login_at)}</td>
                    <td className="px-4 py-3 text-gray-400">{fmt(u.created_at)}</td>
                    <td className="px-4 py-3">
                      {u.is_admin ? (
                        <span className="rounded-full bg-amber-900/50 text-amber-300 px-2 py-0.5 text-xs font-medium">Admin</span>
                      ) : (
                        <span className="rounded-full bg-gray-800 text-gray-400 px-2 py-0.5 text-xs font-medium">User</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {u.id !== user?.id && (
                        <button
                          onClick={() => handleToggleAdmin(u)}
                          className={`text-xs transition ${
                            u.is_admin
                              ? "text-red-400 hover:text-red-300"
                              : "text-indigo-400 hover:text-indigo-300"
                          }`}
                        >
                          {u.is_admin ? "Revoke admin" : "Make admin"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
