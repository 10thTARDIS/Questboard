/**
 * Profile — lets the user set their display name override and timezone.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import { updateMe } from "../api/auth.js";

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

export default function Profile() {
  const { user, refreshUser } = useAuth();

  const [form, setForm] = useState({
    display_name_override: user?.display_name_override ?? "",
    timezone: user?.timezone ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateMe({
        display_name_override: form.display_name_override || null,
        timezone: form.timezone || null,
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

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link to="/dashboard" className="text-gray-500 hover:text-white transition text-sm">
          ← Dashboard
        </Link>
        <span className="text-gray-700">/</span>
        <span className="font-semibold">Profile</span>
      </header>

      <main className="mx-auto max-w-lg px-6 py-8">
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-lg font-bold mb-1">Your Profile</h2>
          <p className="text-sm text-gray-400 mb-6">
            OIDC display name: <span className="text-gray-300">{user?.display_name}</span>
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">
                Display name override
              </label>
              <input
                type="text"
                placeholder={user?.display_name ?? ""}
                value={form.display_name_override}
                onChange={(e) =>
                  setForm((f) => ({ ...f, display_name_override: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                Leave blank to use your OIDC display name.
              </p>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Timezone</label>
              <select
                value={form.timezone}
                onChange={(e) =>
                  setForm((f) => ({ ...f, timezone: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">— Use browser default —</option>
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
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
      </main>
    </div>
  );
}
