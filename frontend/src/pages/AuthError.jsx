import { useSearchParams, Link } from "react-router-dom";

/**
 * Shown when the OIDC auth flow fails (bad state, provider error, invite code
 * mismatch, etc.).  The backend redirects here with ?message=... so the user
 * sees a human-readable explanation instead of raw JSON.
 */
export default function AuthError() {
  const [params] = useSearchParams();
  const message = params.get("message") || "An unexpected authentication error occurred.";

  return (
    <div className="min-h-screen flex items-center justify-center bg-white dark:bg-gray-950 px-4">
      <div className="max-w-md w-full bg-gray-50 dark:bg-gray-900 rounded-2xl shadow-xl p-8 text-center">
        <div className="text-red-400 text-5xl mb-4">⚠</div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Sign-in failed</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-6">{message}</p>
        <Link
          to="/login"
          className="inline-block bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 px-6 rounded-lg transition-colors"
        >
          Back to login
        </Link>
      </div>
    </div>
  );
}
