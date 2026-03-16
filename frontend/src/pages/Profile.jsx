/**
 * Profile — lets the user set their display name override, timezone,
 * and link/unlink external platform accounts (Discord, Matrix).
 */

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import NavBar from "../components/NavBar.jsx";
import { updateMe } from "../api/auth.js";
import { addPlatformLink, fetchPlatformLinks, removePlatformLink } from "../api/users.js";

// Common IANA timezone list (subset of most-used zones)
const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "America/Honolulu",
  "America/Toronto",
  "America/Vancouver",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Dublin",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Amsterdam",
  "Europe/Rome",
  "Europe/Madrid",
  "Europe/Stockholm",
  "Europe/Warsaw",
  "Europe/Bucharest",
  "Europe/Helsinki",
  "Europe/Istanbul",
  "Europe/Moscow",
  "Asia/Dubai",
  "Asia/Karachi",
  "Asia/Kolkata",
  "Asia/Dhaka",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Jakarta",
  "Australia/Sydney",
  "Australia/Melbourne",
  "Australia/Perth",
  "Pacific/Auckland",
];

const PLATFORM_LABELS = { discord: "Discord", matrix: "Matrix" };

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [searchParams] = useSearchParams();

  const [form, setForm] = useState({
    display_name_override: user?.display_name_override ?? "",
    timezone: user?.timezone ?? "",
    recap_email_opt_in: user?.recap_email_opt_in ?? false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  // Platform links
  const [links, setLinks] = useState([]);
  const [linksLoading, setLinksLoading] = useState(true);
  const [linkForm, setLinkForm] = useState({ platform: "discord", platform_user_id: "" });
  const [linkError, setLinkError] = useState(null);
  const [linkSaving, setLinkSaving] = useState(false);
  const [linkSuccess, setLinkSuccess] = useState(
    searchParams.get("linked") ? `${searchParams.get("linked")} account linked successfully!` : null
  );

  useEffect(() => {
    fetchPlatformLinks()
      .then(setLinks)
      .catch(() => {})
      .finally(() => setLinksLoading(false));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateMe({
        display_name_override: form.display_name_override || null,
        timezone: form.timezone || null,
        recap_email_opt_in: form.recap_email_opt_in,
      });
      if (refreshUser) await refreshUser();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAddLink = async (e) => {
    e.preventDefault();
    if (!linkForm.platform_user_id.trim()) return;
    setLinkSaving(true);
    setLinkError(null);
    try {
      const newLink = await addPlatformLink(linkForm.platform, linkForm.platform_user_id.trim());
      setLinks((prev) => {
        const filtered = prev.filter((l) => l.platform !== newLink.platform);
        return [...filtered, newLink];
      });
      setLinkForm((f) => ({ ...f, platform_user_id: "" }));
    } catch (e) {
      setLinkError(e.message);
    } finally {
      setLinkSaving(false);
    }
  };

  const handleRemoveLink = async (platform) => {
    try {
      await removePlatformLink(platform);
      setLinks((prev) => prev.filter((l) => l.platform !== platform));
    } catch (e) {
      setLinkError(e.message);
    }
  };

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-white">
      <header className="border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/dashboard" className="text-gray-500 hover:text-gray-900 dark:hover:text-white transition text-sm">← Dashboard</Link>
          <span className="text-gray-400 dark:text-gray-700">/</span>
          <span className="font-semibold">Profile</span>
        </div>
        <NavBar />
      </header>

      <main className="mx-auto max-w-lg px-6 py-8 space-y-6">
        {/* Profile settings */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-6">
          <h2 className="text-lg font-bold mb-1">Your Profile</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
            OIDC display name: <span className="text-gray-700 dark:text-gray-300">{user?.display_name}</span>
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-gray-600 dark:text-gray-400 block mb-1">
                Display name override
              </label>
              <input
                type="text"
                placeholder={user?.display_name ?? ""}
                value={form.display_name_override}
                onChange={(e) =>
                  setForm((f) => ({ ...f, display_name_override: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                Leave blank to use your OIDC display name.
              </p>
            </div>

            <div>
              <label className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Timezone</label>
              <select
                value={form.timezone}
                onChange={(e) =>
                  setForm((f) => ({ ...f, timezone: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">— Use browser default —</option>
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>

            <div className="flex items-start gap-3">
              <input
                id="recap_email_opt_in"
                type="checkbox"
                checked={form.recap_email_opt_in}
                onChange={(e) => setForm((f) => ({ ...f, recap_email_opt_in: e.target.checked }))}
                className="mt-0.5 h-4 w-4 rounded border-gray-400 dark:border-gray-600 bg-gray-100 dark:bg-gray-800 text-indigo-500 focus:ring-indigo-500"
              />
              <div>
                <label htmlFor="recap_email_opt_in" className="text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                  Receive post-session recap emails
                </label>
                <p className="text-xs text-gray-500 mt-0.5">
                  When the bot uploads a session transcript, receive an AI-generated summary
                  to your account email. Requires SMTP to be configured by an admin.
                </p>
              </div>
            </div>

            {error && <p className="text-sm text-red-400">{error}</p>}
            {saved && <p className="text-sm text-green-400">Saved!</p>}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
              >
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        </div>

        {/* Connected accounts */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-6">
          <h2 className="text-lg font-bold mb-1">Connected Accounts</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Link your platform accounts so the Discord bot can identify you.
          </p>
          {linkSuccess && (
            <p className="mb-4 text-sm text-green-400">{linkSuccess}</p>
          )}

          {linksLoading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : (
            <div className="space-y-2 mb-4">
              {links.length === 0 && (
                <p className="text-sm text-gray-500">No accounts linked yet.</p>
              )}
              {links.map((link) => (
                <div
                  key={link.platform}
                  className="flex items-center justify-between rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2"
                >
                  <div>
                    <span className="text-sm font-medium">
                      {PLATFORM_LABELS[link.platform] ?? link.platform}
                    </span>
                    <span className="ml-2 text-sm text-gray-600 dark:text-gray-400 font-mono">
                      {link.platform_user_id}
                    </span>
                    {link.verified_at && (
                      <span className="ml-2 text-xs text-green-500">verified</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemoveLink(link.platform)}
                    className="text-xs text-red-400 hover:text-red-300 transition"
                  >
                    Unlink
                  </button>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleAddLink} className="space-y-3">
            <div className="flex gap-2">
              <select
                value={linkForm.platform}
                onChange={(e) => setLinkForm((f) => ({ ...f, platform: e.target.value }))}
                className="rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="discord">Discord</option>
                <option value="matrix">Matrix</option>
              </select>
              <input
                type="text"
                placeholder={
                  linkForm.platform === "discord" ? "Discord user ID" : "Matrix user ID"
                }
                value={linkForm.platform_user_id}
                onChange={(e) =>
                  setLinkForm((f) => ({ ...f, platform_user_id: e.target.value }))
                }
                className="flex-1 rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={linkSaving || !linkForm.platform_user_id.trim()}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
              >
                {linkSaving ? "Linking…" : "Link"}
              </button>
            </div>
            {linkForm.platform === "discord" && (
              <p className="text-xs text-gray-500 dark:text-gray-500">
                Enter your Discord user ID (not your username). To find it: enable Developer Mode
                in Discord → Settings → Advanced, then right-click your name and select "Copy User ID".
              </p>
            )}
            {linkError && <p className="text-sm text-red-400">{linkError}</p>}
          </form>
        </div>
      </main>
    </div>
  );
}
