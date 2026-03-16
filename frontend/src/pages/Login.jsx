import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";

export default function Login() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [inviteCode, setInviteCode] = useState("");

  // If already authenticated, skip login
  useEffect(() => {
    if (!loading && user) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, loading, navigate]);

  const handleSignIn = () => {
    const params = inviteCode
      ? `?invite_code=${encodeURIComponent(inviteCode)}`
      : "";
    // Full-page navigation — backend redirects to OIDC provider
    window.location.href = `/auth/login${params}`;
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-gray-600 dark:text-gray-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white dark:bg-gray-950 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-gray-50 dark:bg-gray-900 p-8 shadow-xl">
        <h1 className="mb-2 text-center text-3xl font-bold text-gray-900 dark:text-white">
          Quest Board
        </h1>
        <p className="mb-8 text-center text-sm text-gray-600 dark:text-gray-400">
          TTRPG session scheduling
        </p>

        {/* Invite code field — hidden until the user starts typing */}
        <input
          type="text"
          placeholder="Invite code (if required)"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSignIn(); }}
          className="mb-4 w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-4 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />

        <button
          onClick={handleSignIn}
          className="w-full rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          Sign in with SSO
        </button>
      </div>
    </div>
  );
}
