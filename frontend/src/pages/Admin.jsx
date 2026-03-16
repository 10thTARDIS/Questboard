/**
 * Admin — site administration panel.
 *
 * Sections:
 *  1. Users — list all users with last-login, expandable rows showing
 *             campaign memberships and attendance stats.
 *  2. Notification Settings — configure global Discord webhook fallback
 *             and SMTP for email notifications.
 */

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import NavBar from "../components/NavBar.jsx";
import { fetchAdminUsers, setAdminStatus } from "../api/auth.js";
import {
  fetchAdminUserDetail,
  fetchNotificationSettings,
  saveNotificationSettings,
  sendTestEmail,
} from "../api/sessions.js";
import { fetchBotSettings, pingBot, regenerateBotApiKey, saveBotSettings } from "../api/users.js";

function fmt(iso) {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── User drill-down row ────────────────────────────────────────────────────────

function UserDetailPanel({ userId }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAdminUserDetail(userId)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading) return <p className="text-xs text-gray-500 py-2">Loading…</p>;
  if (error) return <p className="text-xs text-red-400 py-2">{error}</p>;
  if (!detail || detail.campaigns.length === 0) {
    return <p className="text-xs text-gray-600 py-2">No campaign memberships.</p>;
  }

  return (
    <table className="w-full text-xs mt-2">
      <thead>
        <tr className="text-left text-gray-500 border-b border-gray-300 dark:border-gray-700">
          <th className="py-1 pr-4 font-medium">Campaign</th>
          <th className="py-1 pr-4 font-medium">Role</th>
          <th className="py-1 pr-4 font-medium">Joined</th>
          <th className="py-1 font-medium">Attendance</th>
        </tr>
      </thead>
      <tbody>
        {detail.campaigns.map((c) => (
          <tr key={c.campaign_id} className="border-b border-gray-200/50 dark:border-gray-800/50">
            <td className="py-1.5 pr-4 text-gray-700 dark:text-gray-300">{c.campaign_name}</td>
            <td className="py-1.5 pr-4 text-gray-600 dark:text-gray-400 capitalize">{c.role}</td>
            <td className="py-1.5 pr-4 text-gray-500">{fmt(c.joined_at)}</td>
            <td className="py-1.5 text-gray-600 dark:text-gray-400">
              {c.attended_count}/{c.session_count}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Notification settings section ─────────────────────────────────────────────

function NotificationSettings() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testBusy, setTestBusy] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [smtpForm, setSmtpForm] = useState({
    host: "", port: 587, username: "", password: "", from_address: "", use_tls: true,
  });
  const [webhookUrl, setWebhookUrl] = useState("");

  useEffect(() => {
    fetchNotificationSettings()
      .then((s) => {
        setSettings(s);
        setSmtpForm({
          host: s.smtp.host || "",
          port: s.smtp.port || 587,
          username: s.smtp.username || "",
          password: "",  // never pre-filled
          from_address: s.smtp.from_address || "",
          use_tls: s.smtp.use_tls !== false,
        });
        setWebhookUrl(s.discord_webhook_url || "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await saveNotificationSettings({
        smtp: smtpForm,
        discord_webhook_url: webhookUrl || null,
      });
      setSettings(updated);
      setSuccess("Settings saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    setTestBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await sendTestEmail();
      setSuccess("Test email queued — check your inbox.");
    } catch (e) {
      setError(e.message);
    } finally {
      setTestBusy(false);
    }
  };

  if (loading) return <p className="text-sm text-gray-500">Loading settings…</p>;

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {error && (
        <p className="rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      {success && (
        <p className="rounded-lg bg-green-900/30 border border-green-800 px-4 py-2 text-sm text-green-300">
          {success}
        </p>
      )}

      {/* Discord webhook */}
      <div>
        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
          Global Discord Webhook URL (fallback for campaigns without a webhook set)
        </label>
        <input
          type="url"
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
          placeholder="https://discord.com/api/webhooks/…"
          className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* SMTP */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">
          SMTP (Email Notifications)
          {settings?.smtp?.configured && (
            <span className="ml-2 rounded-full bg-green-900/50 text-green-400 px-2 py-0.5 normal-case font-normal">
              Configured
            </span>
          )}
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">Host</label>
            <input
              type="text"
              value={smtpForm.host}
              onChange={(e) => setSmtpForm((f) => ({ ...f, host: e.target.value }))}
              placeholder="smtp.example.com"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">Port</label>
            <input
              type="number"
              value={smtpForm.port}
              onChange={(e) => setSmtpForm((f) => ({ ...f, port: parseInt(e.target.value) || 587 }))}
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">Username</label>
            <input
              type="text"
              value={smtpForm.username}
              onChange={(e) => setSmtpForm((f) => ({ ...f, username: e.target.value }))}
              autoComplete="off"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">
              Password {settings?.smtp?.configured && <span className="text-gray-500 dark:text-gray-600">(leave blank to keep current)</span>}
            </label>
            <input
              type="password"
              value={smtpForm.password}
              onChange={(e) => setSmtpForm((f) => ({ ...f, password: e.target.value }))}
              autoComplete="new-password"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">From Address</label>
            <input
              type="email"
              value={smtpForm.from_address}
              onChange={(e) => setSmtpForm((f) => ({ ...f, from_address: e.target.value }))}
              placeholder="questboard@example.com"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={smtpForm.use_tls}
            onChange={(e) => setSmtpForm((f) => ({ ...f, use_tls: e.target.checked }))}
            className="accent-indigo-500"
          />
          <span className="text-xs text-gray-600 dark:text-gray-400">Use STARTTLS</span>
        </label>

        {settings?.smtp?.configured && (
          <div>
            <button
              type="button"
              onClick={handleTestEmail}
              disabled={testBusy}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition disabled:opacity-50"
            >
              {testBusy ? "Sending…" : "Send test email to my address"}
            </button>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
        >
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </div>
    </form>
  );
}

// ── Bot settings section ───────────────────────────────────────────────────────

function BotSettings() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [newKey, setNewKey] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [pingStatus, setPingStatus] = useState(null); // null | {reachable, latency_ms?, error?}
  const [pinging, setPinging] = useState(false);

  const [form, setForm] = useState({
    bot_token: "",
    bot_url: "",
    whisper_endpoint_url: "",
    whisper_api_key: "",
    llm_endpoint_url: "",
    llm_api_key: "",
    llm_model: "",
  });

  const checkConnection = async () => {
    setPinging(true);
    setPingStatus(null);
    try {
      const result = await pingBot();
      setPingStatus(result);
    } catch {
      setPingStatus({ reachable: false, error: "Request failed" });
    } finally {
      setPinging(false);
    }
  };

  useEffect(() => {
    fetchBotSettings()
      .then((s) => {
        setSettings(s);
        setForm((f) => ({
          ...f,
          bot_url: s.bot_url || "",
          whisper_endpoint_url: s.whisper_endpoint_url || "",
          llm_endpoint_url: s.llm_endpoint_url || "",
          llm_model: s.llm_model || "",
        }));
        if (s.bot_url) {
          // Auto-check on load if a URL is configured
          pingBot()
            .then(setPingStatus)
            .catch(() => setPingStatus({ reachable: false, error: "Request failed" }));
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await saveBotSettings(form);
      setSettings(updated);
      setSuccess("Settings saved.");
      setForm((f) => ({ ...f, bot_token: "", whisper_api_key: "", llm_api_key: "" }));
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerate = async () => {
    if (!confirm("Regenerate the bot API key? The current key will stop working immediately.")) return;
    setRegenerating(true);
    setError(null);
    setNewKey(null);
    try {
      const result = await regenerateBotApiKey();
      setNewKey(result.api_key);
      setSettings((s) => s ? { ...s, api_key_configured: true } : s);
    } catch (e) {
      setError(e.message);
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) return <p className="text-sm text-gray-500">Loading settings…</p>;

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {error && (
        <p className="rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      {success && (
        <p className="rounded-lg bg-green-900/30 border border-green-800 px-4 py-2 text-sm text-green-300">
          {success}
        </p>
      )}

      {/* Bot API key */}
      <div>
        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2">
          Bot API Key
          {settings?.api_key_configured && (
            <span className="ml-2 rounded-full bg-green-900/50 text-green-400 px-2 py-0.5 normal-case font-normal">
              Configured
            </span>
          )}
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-500 mb-3">
          The Discord bot uses this key in every request it makes to Questboard (X-Bot-Key header).
          The key is only shown once when generated.
        </p>
        {newKey && (
          <div className="rounded-lg bg-yellow-900/30 border border-yellow-700 px-4 py-3 mb-3">
            <p className="text-xs text-yellow-300 font-medium mb-1">New API key — copy it now, it won't be shown again:</p>
            <code className="text-xs font-mono text-yellow-200 break-all">{newKey}</code>
          </div>
        )}
        <button
          type="button"
          onClick={handleRegenerate}
          disabled={regenerating}
          className="rounded-lg bg-gray-200 dark:bg-gray-700 px-4 py-2 text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 transition"
        >
          {regenerating ? "Generating…" : settings?.api_key_configured ? "Regenerate Key" : "Generate Key"}
        </button>
      </div>

      {/* Bot URL */}
      <div>
        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2">
          Bot URL
        </label>
        <p className="text-xs text-gray-500 dark:text-gray-500 mb-2">
          HTTP base URL of the questboard-bot server (e.g. <span className="font-mono">http://questboard-bot:8080</span>).
          When set, campaigns with a Discord Server ID configured will send notifications to the bot
          instead of the Discord webhook.
        </p>
        <input
          type="url"
          value={form.bot_url}
          onChange={(e) => setForm((f) => ({ ...f, bot_url: e.target.value }))}
          placeholder="http://questboard-bot:8080"
          className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={checkConnection}
            disabled={pinging || !form.bot_url}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400 hover:border-gray-400 dark:hover:border-gray-500 disabled:opacity-50 transition"
          >
            {pinging ? "Checking…" : "Check connection"}
          </button>
          {pingStatus && !pinging && (
            pingStatus.reachable ? (
              <span className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400">
                <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                Connected
                {pingStatus.latency_ms != null && (
                  <span className="text-gray-500">({pingStatus.latency_ms} ms)</span>
                )}
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
                <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                Unreachable
                {pingStatus.error && (
                  <span className="text-gray-500">— {pingStatus.error}</span>
                )}
              </span>
            )
          )}
        </div>
      </div>

      {/* Discord bot token */}
      <div>
        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2">
          Discord Bot Token
          {settings?.bot_token_configured && (
            <span className="ml-2 rounded-full bg-green-900/50 text-green-400 px-2 py-0.5 normal-case font-normal">
              Configured
            </span>
          )}
        </p>
        <input
          type="password"
          value={form.bot_token}
          onChange={(e) => setForm((f) => ({ ...f, bot_token: e.target.value }))}
          placeholder={settings?.bot_token_configured ? "Leave blank to keep current" : "Discord bot token"}
          autoComplete="new-password"
          className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* Whisper */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">
          Whisper (Transcription)
          {settings?.whisper_configured && (
            <span className="ml-2 rounded-full bg-green-900/50 text-green-400 px-2 py-0.5 normal-case font-normal">
              Configured
            </span>
          )}
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">Endpoint URL</label>
            <input
              type="url"
              value={form.whisper_endpoint_url}
              onChange={(e) => setForm((f) => ({ ...f, whisper_endpoint_url: e.target.value }))}
              placeholder="https://whisper.example.com"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">
              API Key {settings?.whisper_configured && <span className="text-gray-500 dark:text-gray-600">(leave blank to keep)</span>}
            </label>
            <input
              type="password"
              value={form.whisper_api_key}
              onChange={(e) => setForm((f) => ({ ...f, whisper_api_key: e.target.value }))}
              autoComplete="new-password"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>

      {/* LLM */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">
          LLM (Summarisation)
          {settings?.llm_configured && (
            <span className="ml-2 rounded-full bg-green-900/50 text-green-400 px-2 py-0.5 normal-case font-normal">
              Configured
            </span>
          )}
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">Endpoint URL</label>
            <input
              type="url"
              value={form.llm_endpoint_url}
              onChange={(e) => setForm((f) => ({ ...f, llm_endpoint_url: e.target.value }))}
              placeholder="https://api.openai.com/v1"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">
              API Key {settings?.llm_configured && <span className="text-gray-500 dark:text-gray-600">(leave blank to keep)</span>}
            </label>
            <input
              type="password"
              value={form.llm_api_key}
              onChange={(e) => setForm((f) => ({ ...f, llm_api_key: e.target.value }))}
              autoComplete="new-password"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-gray-500 dark:text-gray-500 mb-1">Model</label>
            <input
              type="text"
              value={form.llm_model}
              onChange={(e) => setForm((f) => ({ ...f, llm_model: e.target.value }))}
              placeholder="gpt-4o"
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
        >
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </div>
    </form>
  );
}


// ── Main Admin page ────────────────────────────────────────────────────────────

export default function Admin() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [expandedUser, setExpandedUser] = useState(null);
  const [activeTab, setActiveTab] = useState("users"); // "users" | "settings" | "bot"

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

  const toggleExpand = (userId) => {
    setExpandedUser((prev) => (prev === userId ? null : userId));
  };

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-white">
      <header className="border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/dashboard" className="text-gray-500 hover:text-gray-900 dark:hover:text-white transition text-sm">
            ← Dashboard
          </Link>
          <span className="text-gray-400 dark:text-gray-700">/</span>
          <span className="font-semibold">Admin</span>
        </div>
        <NavBar />
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-800">
          {[["users", "Users"], ["settings", "Notification Settings"], ["bot", "Bot Settings"]].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`px-4 py-2 text-sm font-medium transition border-b-2 -mb-px ${
                activeTab === key
                  ? "border-indigo-500 text-gray-900 dark:text-white"
                  : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Users tab */}
        {activeTab === "users" && (
          <>
            {actionError && (
              <p className="mb-4 rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
                {actionError}
              </p>
            )}

            {loading && <p className="text-gray-500 text-sm">Loading users…</p>}
            {error && <p className="text-red-400 text-sm">{error}</p>}

            {!loading && !error && (
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-800 text-left text-gray-600 dark:text-gray-400 text-xs">
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
                      <>
                        <tr
                          key={u.id}
                          className="border-b border-gray-200/50 dark:border-gray-800/50 hover:bg-gray-200/30 dark:hover:bg-gray-800/30 cursor-pointer"
                          onClick={() => toggleExpand(u.id)}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 dark:text-gray-500 text-xs select-none">
                                {expandedUser === u.id ? "▾" : "▸"}
                              </span>
                              <div>
                                <div className="font-medium">{u.effective_display_name}</div>
                                {u.display_name_override && (
                                  <div className="text-xs text-gray-500">{u.display_name}</div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{u.email ?? "—"}</td>
                          <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{fmt(u.last_login_at)}</td>
                          <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{fmt(u.created_at)}</td>
                          <td className="px-4 py-3">
                            {u.is_admin ? (
                              <span className="rounded-full bg-amber-900/50 text-amber-300 px-2 py-0.5 text-xs font-medium">Admin</span>
                            ) : (
                              <span className="rounded-full bg-gray-200 dark:bg-gray-800 text-gray-600 dark:text-gray-400 px-2 py-0.5 text-xs font-medium">User</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
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
                        {expandedUser === u.id && (
                          <tr key={`${u.id}-detail`} className="bg-gray-50/50 dark:bg-gray-900/50 border-b border-gray-200/50 dark:border-gray-800/50">
                            <td colSpan={6} className="px-8 py-3">
                              <UserDetailPanel userId={u.id} />
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* Notification settings tab */}
        {activeTab === "settings" && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-6">
            <NotificationSettings />
          </div>
        )}

        {/* Bot settings tab */}
        {activeTab === "bot" && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-6">
            <BotSettings />
          </div>
        )}
      </main>
    </div>
  );
}
