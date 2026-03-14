/**
 * CampaignDetail — detail page for a single campaign.
 *
 * Shows campaign info, invite code, member roster, and session list.
 * GMs see additional controls: edit campaign, regenerate invite code,
 * remove members, and create new sessions.
 *
 * The page fetches campaign data, members, and sessions in parallel to
 * minimise load time.  All mutations update local state optimistically or
 * refresh from the server response to stay consistent.
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import {
  deleteCampaign,
  fetchCampaign,
  fetchMembers,
  regenerateInviteCode,
  removeMember,
  updateCampaign,
  updateMember,
} from "../api/campaigns.js";
import { createSession, fetchSessions } from "../api/sessions.js";

const COMMON_TIMEZONES = [
  "UTC","America/New_York","America/Chicago","America/Denver","America/Los_Angeles",
  "America/Toronto","America/Sao_Paulo","Europe/London","Europe/Dublin","Europe/Paris",
  "Europe/Berlin","Europe/Amsterdam","Europe/Moscow","Asia/Dubai","Asia/Kolkata",
  "Asia/Singapore","Asia/Shanghai","Asia/Tokyo","Australia/Sydney","Pacific/Auckland",
];

const STATUS_CLASSES = {
  proposed:  "bg-blue-900/50 text-blue-300",
  confirmed: "bg-green-900/50 text-green-300",
  completed: "bg-gray-800 text-gray-400",
  cancelled: "bg-red-900/40 text-red-400",
};

const MODE_LABELS = {
  vote: "Pending vote",
  direct: "Direct",
  tentative: "Tentative",
};

function fmt(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function CampaignDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [campaign, setCampaign] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Derived: is the current user the GM?
  const isGm = members.some(
    (m) => m.user_id === user?.id && m.role === "gm"
  );

  // Edit form state
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [editError, setEditError] = useState(null);
  const [saving, setSaving] = useState(false);

  // Character name editing state
  const [editingCharName, setEditingCharName] = useState(false);
  const [charNameInput, setCharNameInput] = useState("");
  const [savingCharName, setSavingCharName] = useState(false);

  // Misc action state
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState(null);

  // Sessions state
  const [sessions, setSessions] = useState([]);
  const [showNewSession, setShowNewSession] = useState(false);
  const [sessionForm, setSessionForm] = useState({
    title: "", description: "", scheduling_mode: "vote",
    times: ["", ""],  // local datetime-local strings
  });
  const [sessionError, setSessionError] = useState(null);
  const [creatingSession, setCreatingSession] = useState(false);

  useEffect(() => {
    Promise.all([fetchCampaign(id), fetchMembers(id), fetchSessions(id)])
      .then(([c, m, s]) => {
        setCampaign(c);
        setMembers(m);
        setSessions(s);
        setEditForm({
          name: c.name,
          game_system: c.game_system ?? "",
          description: c.description ?? "",
          discord_webhook_url: c.discord_webhook_url ?? "",
          timezone: c.timezone ?? "",
          reminder_offsets_minutes: (c.reminder_offsets_minutes ?? []).join(", "),
        });
        const myMember = m.find((mem) => mem.user_id === user?.id);
        setCharNameInput(myMember?.character_name ?? "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setEditError(null);
    try {
      // Parse reminder_offsets_minutes from comma-separated string
      let reminders = null;
      if (editForm.reminder_offsets_minutes.trim()) {
        reminders = editForm.reminder_offsets_minutes
          .split(",")
          .map((s) => parseInt(s.trim(), 10))
          .filter((n) => !isNaN(n) && n > 0);
        if (reminders.length === 0) reminders = null;
      }
      const updated = await updateCampaign(id, {
        name: editForm.name,
        game_system: editForm.game_system || null,
        description: editForm.description || null,
        discord_webhook_url: editForm.discord_webhook_url || null,
        timezone: editForm.timezone || null,
        reminder_offsets_minutes: reminders,
      });
      setCampaign(updated);
      setEditing(false);
    } catch (e) {
      setEditError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCharName = async (e) => {
    e.preventDefault();
    setSavingCharName(true);
    try {
      const updated = await updateMember(id, user.id, {
        character_name: charNameInput.trim() || null,
      });
      setMembers((prev) =>
        prev.map((m) => (m.user_id === user.id ? { ...m, character_name: updated.character_name } : m))
      );
      setEditingCharName(false);
    } catch (e) {
      setActionError(e.message);
    } finally {
      setSavingCharName(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${campaign.name}"? This cannot be undone.`)) return;
    try {
      await deleteCampaign(id);
      navigate("/dashboard");
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleRegenerate = async () => {
    if (!confirm("Generate a new invite code? The old one will stop working.")) return;
    try {
      const updated = await regenerateInviteCode(id);
      setCampaign(updated);
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(campaign.invite_code ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRemoveMember = async (memberId, displayName) => {
    if (!confirm(`Remove ${displayName} from this campaign?`)) return;
    try {
      await removeMember(id, memberId);
      setMembers((prev) => prev.filter((m) => m.user_id !== memberId));
    } catch (e) {
      setActionError(e.message);
    }
  };

  // ── Session creation ─────────────────────────────────────────────────────────

  // Vote mode supports 2–5 slots (user controls count); direct/tentative use exactly 1.
  const sessionTimeCount = sessionForm.scheduling_mode === "vote" ? sessionForm.times.length : 1;

  const handleCreateSession = async (e) => {
    e.preventDefault();
    setCreatingSession(true);
    setSessionError(null);
    try {
      const times = sessionForm.times
        .slice(0, sessionTimeCount)
        .filter(Boolean)
        .map((t) => new Date(t).toISOString());

      if (times.length < sessionTimeCount) {
        throw new Error("Please fill in all proposed times");
      }

      const created = await createSession(id, {
        title: sessionForm.title || null,
        description: sessionForm.description || null,
        scheduling_mode: sessionForm.scheduling_mode,
        proposed_times: times,
      });
      setSessions((prev) => [created, ...prev]);
      setShowNewSession(false);
      setSessionForm({ title: "", description: "", scheduling_mode: "vote", times: ["", ""] });
    } catch (e) {
      setSessionError(e.message);
    } finally {
      setCreatingSession(false);
    }
  };

  const setTime = (idx, val) =>
    setSessionForm((f) => {
      const times = [...f.times];
      times[idx] = val;
      return { ...f, times };
    });

  const addTimeSlot = () =>
    setSessionForm((f) => ({ ...f, times: [...f.times, ""] }));

  const removeTimeSlot = (idx) =>
    setSessionForm((f) => ({ ...f, times: f.times.filter((_, i) => i !== idx) }));

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-gray-950 gap-4">
        <p className="text-red-400">{error ?? "Campaign not found."}</p>
        <Link to="/dashboard" className="text-sm text-indigo-400 hover:underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link to="/dashboard" className="text-gray-500 hover:text-white transition text-sm">
          ← Campaigns
        </Link>
        <span className="text-gray-700">/</span>
        <span className="font-semibold">{campaign.name}</span>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 space-y-8">
        {actionError && (
          <p className="rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
            {actionError}
          </p>
        )}

        {/* Campaign info */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          {!editing ? (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-bold">{campaign.name}</h2>
                  {campaign.game_system && (
                    <p className="text-sm text-gray-400 mt-1">{campaign.game_system}</p>
                  )}
                  {campaign.description && (
                    <p className="mt-3 text-sm text-gray-300">{campaign.description}</p>
                  )}
                </div>
                {isGm && (
                  <div className="flex flex-wrap gap-2 ml-4 shrink-0">
                    <button
                      onClick={() => setEditing(true)}
                      className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs hover:border-gray-500 transition"
                    >
                      Edit
                    </button>
                    <button
                      onClick={handleDelete}
                      className="rounded-lg border border-red-900 px-3 py-1.5 text-xs text-red-400 hover:border-red-700 transition"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <form onSubmit={handleSave} className="space-y-3">
              <h3 className="font-medium">Edit Campaign</h3>
              <input
                required
                placeholder="Campaign name"
                value={editForm.name}
                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <input
                placeholder="Game system"
                value={editForm.game_system}
                onChange={(e) => setEditForm((f) => ({ ...f, game_system: e.target.value }))}
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <textarea
                placeholder="Description"
                rows={3}
                value={editForm.description}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
              <input
                placeholder="Discord webhook URL (optional)"
                value={editForm.discord_webhook_url}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, discord_webhook_url: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <div>
                <label className="text-xs text-gray-400 block mb-1">Campaign timezone</label>
                <select
                  value={editForm.timezone}
                  onChange={(e) => setEditForm((f) => ({ ...f, timezone: e.target.value }))}
                  className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">— Use server default —</option>
                  {COMMON_TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Reminder offsets (minutes before session, comma-separated)
                </label>
                <input
                  placeholder="e.g. 10080, 1440, 60 (= 7d, 24h, 1h)"
                  value={editForm.reminder_offsets_minutes}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, reminder_offsets_minutes: e.target.value }))
                  }
                  className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {editError && <p className="text-sm text-red-400">{editError}</p>}
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          )}
        </section>

        {/* Invite code */}
        {campaign.invite_code && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <h3 className="text-sm font-medium text-gray-400 mb-3">Invite Code</h3>
            <div className="flex items-center gap-3">
              <code className="flex-1 rounded-lg bg-gray-800 px-4 py-2 font-mono text-sm tracking-widest">
                {campaign.invite_code}
              </code>
              <button
                onClick={handleCopyCode}
                className="rounded-lg border border-gray-700 px-3 py-2 text-xs hover:border-gray-500 transition"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
              {isGm && (
                <button
                  onClick={handleRegenerate}
                  className="rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-400 hover:border-gray-500 transition"
                >
                  Regenerate
                </button>
              )}
            </div>
          </section>
        )}

        {/* Members */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h3 className="text-sm font-medium text-gray-400 mb-4">
            Members ({members.length})
          </h3>
          <ul className="space-y-2">
            {members.map((m) => (
              <li
                key={m.user_id}
                className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-gray-800/50"
              >
                <div className="flex items-center gap-3">
                  {m.avatar_url ? (
                    <img
                      src={m.avatar_url}
                      alt=""
                      className="h-7 w-7 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-7 w-7 rounded-full bg-gray-700 flex items-center justify-center text-xs font-medium">
                      {m.display_name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div>
                    <span className="text-sm">{m.display_name}</span>
                    {m.character_name && (
                      <span className="ml-1.5 text-xs text-indigo-400">as {m.character_name}</span>
                    )}
                    {m.user_id === user?.id && (
                      <span className="ml-1.5 text-xs text-gray-500">(you)</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      m.role === "gm"
                        ? "bg-amber-900/50 text-amber-300"
                        : "bg-gray-800 text-gray-400"
                    }`}
                  >
                    {m.role === "gm" ? "GM" : "Player"}
                  </span>
                  {m.user_id === user?.id && (
                    editingCharName ? (
                      <form onSubmit={handleSaveCharName} className="flex items-center gap-1">
                        <input
                          autoFocus
                          placeholder="Character name"
                          value={charNameInput}
                          onChange={(e) => setCharNameInput(e.target.value)}
                          className="rounded bg-gray-700 px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 w-32"
                        />
                        <button type="submit" disabled={savingCharName} className="text-xs text-indigo-400 hover:text-indigo-300 transition">
                          {savingCharName ? "…" : "Save"}
                        </button>
                        <button type="button" onClick={() => setEditingCharName(false)} className="text-xs text-gray-500 hover:text-gray-300 transition">
                          ✕
                        </button>
                      </form>
                    ) : (
                      <button
                        onClick={() => setEditingCharName(true)}
                        className="text-xs text-gray-500 hover:text-indigo-400 transition"
                      >
                        {m.character_name ? "Edit character" : "Set character"}
                      </button>
                    )
                  )}
                  {isGm && m.user_id !== user?.id && (
                    <button
                      onClick={() => handleRemoveMember(m.user_id, m.display_name)}
                      className="text-xs text-gray-600 hover:text-red-400 transition"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* Sessions */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-400">
              Sessions ({sessions.length})
            </h3>
            {isGm && (
              <button
                onClick={() => setShowNewSession((v) => !v)}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 transition"
              >
                {showNewSession ? "Cancel" : "+ New Session"}
              </button>
            )}
          </div>

          {/* New-session form */}
          {showNewSession && (
            <form
              onSubmit={handleCreateSession}
              className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3"
            >
              <h4 className="font-medium text-sm">New Session</h4>
              <input
                placeholder="Title (optional)"
                value={sessionForm.title}
                onChange={(e) =>
                  setSessionForm((f) => ({ ...f, title: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <textarea
                placeholder="Description (optional)"
                rows={2}
                value={sessionForm.description}
                onChange={(e) =>
                  setSessionForm((f) => ({ ...f, description: e.target.value }))
                }
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
              <div>
                <label className="text-xs text-gray-400 mb-1.5 block">
                  Scheduling mode
                </label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: "vote", label: "Vote (2–5 slots)" },
                    { value: "direct", label: "Direct (auto-confirm)" },
                    { value: "tentative", label: "Tentative" },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() =>
                        setSessionForm((f) => ({
                          ...f,
                          scheduling_mode: opt.value,
                          times: opt.value === "vote" ? ["", ""] : [""],
                        }))
                      }
                      className={`rounded-lg px-3 py-1.5 text-xs transition ${
                        sessionForm.scheduling_mode === opt.value
                          ? "bg-indigo-600 text-white"
                          : "border border-gray-700 text-gray-400 hover:border-gray-500"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs text-gray-400 block">
                  {sessionForm.scheduling_mode === "vote"
                    ? "Proposed times"
                    : "Session time"}
                </label>
                {sessionForm.times
                  .slice(0, sessionTimeCount)
                  .map((t, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input
                        type="datetime-local"
                        value={t}
                        onChange={(e) => setTime(idx, e.target.value)}
                        className="flex-1 rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      {sessionForm.scheduling_mode === "vote" &&
                        sessionForm.times.length > 2 && (
                          <button
                            type="button"
                            onClick={() => removeTimeSlot(idx)}
                            className="text-gray-600 hover:text-red-400 text-xs transition"
                          >
                            ✕
                          </button>
                        )}
                    </div>
                  ))}
                {sessionForm.scheduling_mode === "vote" &&
                  sessionForm.times.length < 5 && (
                    <button
                      type="button"
                      onClick={addTimeSlot}
                      className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                    >
                      + Add time slot
                    </button>
                  )}
              </div>

              {sessionError && (
                <p className="text-sm text-red-400">{sessionError}</p>
              )}
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowNewSession(false);
                    setSessionForm({
                      title: "",
                      description: "",
                      scheduling_mode: "vote",
                      times: ["", ""],
                    });
                    setSessionError(null);
                  }}
                  className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingSession}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
                >
                  {creatingSession ? "Creating…" : "Create Session"}
                </button>
              </div>
            </form>
          )}

          {/* Session list */}
          {sessions.length === 0 && !showNewSession && (
            <p className="text-sm text-gray-600 py-4 text-center">
              No sessions yet.{isGm ? " Create one above." : ""}
            </p>
          )}
          <ul className="space-y-2">
            {sessions.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/sessions/${s.id}`}
                  className="flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900 px-4 py-3 hover:border-gray-700 transition"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">
                      {s.title ?? "Untitled Session"}
                    </p>
                    {s.confirmed_time ? (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {fmt(s.confirmed_time)}
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {MODE_LABELS[s.scheduling_mode] ?? s.scheduling_mode}
                      </p>
                    )}
                  </div>
                  <span
                    className={`ml-3 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                      STATUS_CLASSES[s.status] ?? "bg-gray-800 text-gray-400"
                    }`}
                  >
                    {s.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
