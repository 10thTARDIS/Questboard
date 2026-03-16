/**
 * NavBar — right-side user navigation shown in every page header.
 *
 * Renders: display name · Profile · Admin (if admin) · theme toggle · Sign out
 */

import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import { useTheme } from "../hooks/useTheme.jsx";

export default function NavBar() {
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const displayName = user?.effective_display_name ?? user?.display_name;

  return (
    <div className="flex items-center gap-3 shrink-0">
      {displayName && (
        <span className="text-sm text-gray-600 dark:text-gray-400 truncate max-w-[140px]">{displayName}</span>
      )}
      <Link to="/profile" className="text-sm text-gray-500 hover:text-gray-900 dark:hover:text-white transition">
        Profile
      </Link>
      {user?.is_admin && (
        <Link to="/admin" className="text-sm text-gray-500 hover:text-gray-900 dark:hover:text-white transition">
          Admin
        </Link>
      )}
      <button
        onClick={toggle}
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="text-sm text-gray-500 hover:text-gray-900 dark:hover:text-white transition"
      >
        {theme === "dark" ? "☀" : "☾"}
      </button>
      <a href="/auth/logout" className="text-sm text-gray-500 hover:text-gray-900 dark:hover:text-white transition">
        Sign out
      </a>
    </div>
  );
}
