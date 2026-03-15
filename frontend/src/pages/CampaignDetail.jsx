/**
 * CampaignDetail — detail page for a single campaign.
 *
 * Two-column layout on large screens (single column on mobile):
 *   Left  — campaign info + members, tabbed sessions, tabbed journal/wiki
 *   Right — milestone timeline
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import {
  createMilestone,
  createLoreEntry,
  deleteCampaign,
  deleteLoreEntry,
  deleteMilestone,
  fetchCampaign,
  fetchCampaignNotes,
  fetchLoreEntries,
  fetchMembers,
  fetchMilestones,
  leaveCampaign,
  regenerateInviteCode,
  removeMember,
  updateCampaign,
  updateLoreEntry,
  updateMember,
  updateMilestone,
} from "../api/campaigns.js";
import { createSession, fetchSessions } from "../api/sessions.js";
import DateTimePicker from "../components/DateTimePicker.jsx";

// ── Constants ─────────────────────────────────────────────────────────────────

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

const UNITS = ["minutes", "hours", "days"];
const UNIT_MULTIPLIER = { minutes: 1, hours: 60, days: 1440 };

const LORE_TYPES = ["location", "faction", "npc", "item", "event", "other"];
const LORE_TYPE_LABELS = {
  location: "Location", faction: "Faction", npc: "NPC",
  item: "Item", event: "Event", other: "Other",
};
const LORE_TYPE_COLOURS = {
  location: "text-emerald-400 bg-emerald-950 border-emerald-800",
  faction:  "text-violet-400 bg-violet-950 border-violet-800",
  npc:      "text-sky-400 bg-sky-950 border-sky-800",
  item:     "text-amber-400 bg-amber-950 border-amber-800",
  event:    "text-rose-400 bg-rose-950 border-rose-800",
  other:    "text-gray-400 bg-gray-900 border-gray-700",
};
const BLANK_LORE = { entry_type: "location", title: "", body: "" };

// ── Helpers ───────────────────────────────────────────────────────────────────

function minutesToReminder(minutes) {
  if (minutes % 1440 === 0) return { value: minutes / 1440, unit: "days" };
  if (minutes % 60 === 0)   return { value: minutes / 60,   unit: "hours" };
  return { value: minutes, unit: "minutes" };
}

function remindersToMinutes(rows) {
  return rows
    .map((r) => Math.round(Number(r.value) * UNIT_MULTIPLIER[r.unit]))
    .filter((n) => n > 0)
    .sort((a, b) => b - a);
}

function fmt(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric",
  });
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
        active
          ? "border-indigo-500 text-white"
          : "border-transparent text-gray-500 hover:text-gray-300"
      }`}
    >
      {children}
    </button>
  );
}

function LoreTypeBadge({ type }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${LORE_TYPE_COLOURS[type] ?? LORE_TYPE_COLOURS.other}`}>
      {LORE_TYPE_LABELS[type] ?? type}
    </span>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function CampaignDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  // ── Core data ──────────────────────────────────────────────────────────────
  const [campaign, setCampaign]   = useState(null);
  const [members, setMembers]     = useState([]);
  const [sessions, setSessions]   = useState([]);
  const [milestones, setMilestones] = useState([]);
  const [notes, setNotes]         = useState([]);
  const [loreEntries, setLoreEntries] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [actionError, setActionError] = useState(null);

  const isGm = members.some((m) => m.user_id === user?.id && m.role === "gm");

  // ── UI state ───────────────────────────────────────────────────────────────
  const [sessionTab, setSessionTab]   = useState("upcoming"); // upcoming | completed | cancelled
  const [contentTab, setContentTab]   = useState("journal");  // journal | wiki
  const [loreTypeFilter, setLoreTypeFilter] = useState("all");
  const [expandedLoreIds, setExpandedLoreIds] = useState(new Set());
  const [showInvite, setShowInvite]   = useState(false);

  // ── Campaign edit ──────────────────────────────────────────────────────────
  const [editing, setEditing]   = useState(false);
  const [editForm, setEditForm] = useState({});
  const [editError, setEditError] = useState(null);
  const [saving, setSaving]     = useState(false);

  // ── Member / character ─────────────────────────────────────────────────────
  const [editingCharName, setEditingCharName]       = useState(false);
  const [charNameInput, setCharNameInput]           = useState("");
  const [charSheetUrlInput, setCharSheetUrlInput]   = useState("");
  const [charSheetNotesInput, setCharSheetNotesInput] = useState("");
  const [savingCharName, setSavingCharName]         = useState(false);
  const [copied, setCopied] = useState(false);

  // ── Sessions ───────────────────────────────────────────────────────────────
  const [showNewSession, setShowNewSession] = useState(false);
  const [sessionForm, setSessionForm] = useState({
    title: "", description: "", scheduling_mode: "vote", times: ["", ""],
  });
  const [sessionError, setSessionError]     = useState(null);
  const [creatingSession, setCreatingSession] = useState(false);

  // ── Milestones ─────────────────────────────────────────────────────────────
  const [showNewMilestone, setShowNewMilestone] = useState(false);
  const [milestoneForm, setMilestoneForm]       = useState({ title: "", description: "", session_id: "", milestone_date: "" });
  const [editingMilestone, setEditingMilestone] = useState(null);
  const [editMilestoneForm, setEditMilestoneForm] = useState({});
  const [milestoneError, setMilestoneError]     = useState(null);
  const [savingMilestone, setSavingMilestone]   = useState(false);

  // ── Lore entries ───────────────────────────────────────────────────────────
  const [showCreateLore, setShowCreateLore]   = useState(false);
  const [loreCreateForm, setLoreCreateForm]   = useState(BLANK_LORE);
  const [loreCreateError, setLoreCreateError] = useState(null);
  const [creatingLore, setCreatingLore]       = useState(false);
  const [editingLoreId, setEditingLoreId]     = useState(null);
  const [loreEditForm, setLoreEditForm]       = useState({});
  const [loreEditError, setLoreEditError]     = useState(null);
  const [savingLore, setSavingLore]           = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      fetchCampaign(id),
      fetchMembers(id),
      fetchSessions(id),
      fetchMilestones(id),
      fetchCampaignNotes(id),
      fetchLoreEntries(id),
    ])
      .then(([c, m, s, ms, n, le]) => {
        setCampaign(c);
        setMembers(m);
        setSessions(s);
        setMilestones(ms ?? []);
        setNotes(n ?? []);
        setLoreEntries(le ?? []);
        setEditForm({
          name: c.name,
          game_system: c.game_system ?? "",
          description: c.description ?? "",
          discord_webhook_url: c.discord_webhook_url ?? "",
          guild_id: c.guild_id ?? "",
          notification_channel_id: c.notification_channel_id ?? "",
          timezone: c.timezone ?? "",
          reminders: (c.reminder_offsets_minutes ?? []).map(minutesToReminder),
          vote_notification_mode: c.vote_notification_mode ?? "",
          vote_auto_close_hours: c.vote_auto_close_hours ?? "",
          recap_email_enabled: c.recap_email_enabled ?? false,
        });
        const myMember = m.find((mem) => mem.user_id === user?.id);
        setCharNameInput(myMember?.character_name ?? "");
        setCharSheetUrlInput(myMember?.character_sheet_url ?? "");
        setCharSheetNotesInput(myMember?.character_sheet_notes ?? "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // ── Campaign handlers ──────────────────────────────────────────────────────
  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setEditError(null);
    try {
      const minutesList = remindersToMinutes(editForm.reminders);
      const autoCloseHours = parseInt(editForm.vote_auto_close_hours, 10);
      const updated = await updateCampaign(id, {
        name: editForm.name,
        game_system: editForm.game_system || null,
        description: editForm.description || null,
        discord_webhook_url: editForm.discord_webhook_url || null,
        guild_id: editForm.guild_id || null,
        notification_channel_id: editForm.notification_channel_id || null,
        timezone: editForm.timezone || null,
        reminder_offsets_minutes: minutesList.length > 0 ? minutesList : null,
        vote_notification_mode: editForm.vote_notification_mode || null,
        vote_auto_close_hours: autoCloseHours > 0 ? autoCloseHours : null,
        recap_email_enabled: editForm.recap_email_enabled,
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
        character_sheet_url: charSheetUrlInput.trim() || null,
        character_sheet_notes: charSheetNotesInput.trim() || null,
      });
      setMembers((prev) =>
        prev.map((m) => m.user_id === user.id ? {
          ...m,
          character_name: updated.character_name,
          character_sheet_url: updated.character_sheet_url,
          character_sheet_notes: updated.character_sheet_notes,
        } : m)
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

  const handleLeaveCampaign = async () => {
    if (!confirm(`Leave "${campaign.name}"? You will need a new invite code to rejoin.`)) return;
    try {
      await leaveCampaign(id);
      navigate("/dashboard");
    } catch (e) {
      setActionError(e.message);
    }
  };

  // ── Milestone handlers ─────────────────────────────────────────────────────
  const handleCreateMilestone = async (e) => {
    e.preventDefault();
    if (!milestoneForm.title.trim()) return;
    setSavingMilestone(true);
    setMilestoneError(null);
    try {
      const created = await createMilestone(id, {
        title: milestoneForm.title.trim(),
        description: milestoneForm.description.trim() || null,
        session_id: milestoneForm.session_id || null,
        milestone_date: milestoneForm.milestone_date
          ? new Date(milestoneForm.milestone_date).toISOString()
          : null,
      });
      setMilestones((prev) => [...prev, created]);
      setMilestoneForm({ title: "", description: "", session_id: "", milestone_date: "" });
      setShowNewMilestone(false);
    } catch (e) {
      setMilestoneError(e.message);
    } finally {
      setSavingMilestone(false);
    }
  };

  const handleUpdateMilestone = async (e, milestoneId) => {
    e.preventDefault();
    setSavingMilestone(true);
    setMilestoneError(null);
    try {
      const updated = await updateMilestone(id, milestoneId, {
        title: editMilestoneForm.title || undefined,
        description: editMilestoneForm.description || null,
        session_id: editMilestoneForm.session_id || null,
        milestone_date: editMilestoneForm.milestone_date
          ? new Date(editMilestoneForm.milestone_date).toISOString()
          : null,
      });
      setMilestones((prev) => prev.map((m) => m.id === milestoneId ? updated : m));
      setEditingMilestone(null);
    } catch (e) {
      setMilestoneError(e.message);
    } finally {
      setSavingMilestone(false);
    }
  };

  const handleDeleteMilestone = async (milestoneId) => {
    if (!confirm("Delete this milestone?")) return;
    try {
      await deleteMilestone(id, milestoneId);
      setMilestones((prev) => prev.filter((m) => m.id !== milestoneId));
    } catch (e) {
      setActionError(e.message);
    }
  };

  // ── Session handlers ───────────────────────────────────────────────────────
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
      if (times.length < sessionTimeCount) throw new Error("Please fill in all proposed times");
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
    setSessionForm((f) => { const times = [...f.times]; times[idx] = val; return { ...f, times }; });
  const addTimeSlot = () =>
    setSessionForm((f) => ({ ...f, times: [...f.times, ""] }));
  const removeTimeSlot = (idx) =>
    setSessionForm((f) => ({ ...f, times: f.times.filter((_, i) => i !== idx) }));

  const reuseAsNewSession = (s) => {
    setSessionForm({
      title: s.title ?? "",
      description: s.description ?? "",
      scheduling_mode: "vote",
      times: ["", ""],
    });
    setShowNewSession(true);
    setSessionTab("upcoming");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // ── Lore handlers ──────────────────────────────────────────────────────────
  const handleCreateLore = async (e) => {
    e.preventDefault();
    setLoreCreateError(null);
    setCreatingLore(true);
    try {
      const created = await createLoreEntry(id, {
        entry_type: loreCreateForm.entry_type,
        title: loreCreateForm.title.trim(),
        body: loreCreateForm.body.trim(),
      });
      setLoreEntries((prev) =>
        [...prev, created].sort((a, b) =>
          a.entry_type.localeCompare(b.entry_type) || a.title.localeCompare(b.title)
        )
      );
      setShowCreateLore(false);
      setLoreCreateForm(BLANK_LORE);
    } catch (err) {
      setLoreCreateError(err.message);
    } finally {
      setCreatingLore(false);
    }
  };

  const handleSaveLore = async (e) => {
    e.preventDefault();
    setLoreEditError(null);
    setSavingLore(true);
    try {
      const updated = await updateLoreEntry(id, editingLoreId, {
        entry_type: loreEditForm.entry_type,
        title: loreEditForm.title.trim(),
        body: loreEditForm.body.trim(),
      });
      setLoreEntries((prev) =>
        prev.map((en) => en.id === editingLoreId ? updated : en)
          .sort((a, b) => a.entry_type.localeCompare(b.entry_type) || a.title.localeCompare(b.title))
      );
      setEditingLoreId(null);
    } catch (err) {
      setLoreEditError(err.message);
    } finally {
      setSavingLore(false);
    }
  };

  const handleDeleteLore = async (entryId) => {
    if (!confirm("Delete this lore entry? This cannot be undone.")) return;
    try {
      await deleteLoreEntry(id, entryId);
      setLoreEntries((prev) => prev.filter((e) => e.id !== entryId));
      if (editingLoreId === entryId) setEditingLoreId(null);
    } catch (err) {
      setActionError(err.message);
    }
  };

  const toggleLoreExpand = (entryId) =>
    setExpandedLoreIds((prev) => {
      const next = new Set(prev);
      next.has(entryId) ? next.delete(entryId) : next.add(entryId);
      return next;
    });

  // ── Loading / error states ─────────────────────────────────────────────────
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
        <Link to="/dashboard" className="text-sm text-indigo-400 hover:underline">Back to dashboard</Link>
      </div>
    );
  }

  // ── Derived ────────────────────────────────────────────────────────────────
  const upcomingSessions  = sessions.filter((s) => s.status === "proposed" || s.status === "confirmed");
  const completedSessions = sessions.filter((s) => s.status === "completed");
  const cancelledSessions = sessions.filter((s) => s.status === "cancelled");
  const filteredLore = loreTypeFilter === "all"
    ? loreEntries
    : loreEntries.filter((e) => e.entry_type === loreTypeFilter);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link to="/dashboard" className="text-gray-500 hover:text-white transition text-sm">
          ← Campaigns
        </Link>
        <span className="text-gray-700">/</span>
        <span className="font-semibold">{campaign.name}</span>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {actionError && (
          <p className="mb-4 rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
            {actionError}
          </p>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6 items-start">

          {/* ══ LEFT COLUMN ══════════════════════════════════════════════════ */}
          <div className="space-y-5">

            {/* ── Panel 1: Campaign info + invite + members ─────────────────── */}
            <section className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
              {!editing ? (
                <div className="p-5">
                  {/* Header row */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h2 className="text-lg font-bold leading-tight">{campaign.name}</h2>
                      {campaign.game_system && (
                        <p className="text-sm text-gray-400 mt-0.5">{campaign.game_system}</p>
                      )}
                      {campaign.description && (
                        <p className="mt-2 text-sm text-gray-300">{campaign.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link
                        to={`/campaigns/${id}/analytics`}
                        className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                      >
                        Analytics
                      </Link>
                      {isGm && (
                        <>
                          <button
                            onClick={() => setEditing(true)}
                            className="rounded-lg border border-gray-700 px-2.5 py-1 text-xs hover:border-gray-500 transition"
                          >
                            Edit
                          </button>
                          <button
                            onClick={handleDelete}
                            className="rounded-lg border border-red-900 px-2.5 py-1 text-xs text-red-400 hover:border-red-700 transition"
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Invite code (collapsible) */}
                  {campaign.invite_code && (
                    <div className="mt-4 border-t border-gray-800 pt-3">
                      <button
                        onClick={() => setShowInvite((v) => !v)}
                        className="text-xs text-gray-500 hover:text-gray-300 transition"
                      >
                        {showInvite ? "▲ Hide invite code" : "▼ Show invite code"}
                      </button>
                      {showInvite && (
                        <div className="flex items-center gap-2 mt-2">
                          <code className="flex-1 rounded bg-gray-800 px-3 py-1.5 font-mono text-xs tracking-widest truncate">
                            {campaign.invite_code}
                          </code>
                          <button
                            onClick={handleCopyCode}
                            className="rounded border border-gray-700 px-2.5 py-1 text-xs hover:border-gray-500 transition shrink-0"
                          >
                            {copied ? "Copied!" : "Copy"}
                          </button>
                          {isGm && (
                            <button
                              onClick={handleRegenerate}
                              className="rounded border border-gray-700 px-2.5 py-1 text-xs text-gray-400 hover:border-gray-500 transition shrink-0"
                            >
                              Regenerate
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Members */}
                  <div className="mt-4 border-t border-gray-800 pt-3">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">
                        Members ({members.length})
                      </p>
                      {!isGm && (
                        <button
                          onClick={handleLeaveCampaign}
                          className="text-xs text-red-500 hover:text-red-400 transition"
                        >
                          Leave
                        </button>
                      )}
                    </div>
                    <ul className="space-y-1">
                      {members.map((m) => (
                        <li key={m.user_id} className="rounded-lg px-2 py-1.5 hover:bg-gray-800/50 transition">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              {m.avatar_url ? (
                                <img src={m.avatar_url} alt="" className="h-6 w-6 rounded-full object-cover shrink-0" />
                              ) : (
                                <div className="h-6 w-6 rounded-full bg-gray-700 flex items-center justify-center text-xs font-medium shrink-0">
                                  {m.display_name[0]?.toUpperCase()}
                                </div>
                              )}
                              <div className="min-w-0">
                                <span className="text-sm">{m.display_name}</span>
                                {m.character_name && (
                                  <span className="ml-1.5 text-xs text-indigo-400">as {m.character_name}</span>
                                )}
                                {m.character_sheet_url && (
                                  <a
                                    href={m.character_sheet_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="ml-1.5 text-xs text-gray-500 hover:text-indigo-400 transition"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    Sheet ↗
                                  </a>
                                )}
                                {m.user_id === user?.id && (
                                  <span className="ml-1.5 text-xs text-gray-600">(you)</span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                m.role === "gm" ? "bg-amber-900/50 text-amber-300" : "bg-gray-800 text-gray-400"
                              }`}>
                                {m.role === "gm" ? "GM" : "Player"}
                              </span>
                              {m.user_id === user?.id && (
                                editingCharName ? (
                                  <form onSubmit={handleSaveCharName} className="mt-1 space-y-1.5 w-48">
                                    <input
                                      autoFocus
                                      placeholder="Character name"
                                      value={charNameInput}
                                      onChange={(e) => setCharNameInput(e.target.value)}
                                      className="w-full rounded bg-gray-700 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                    />
                                    <input
                                      type="url"
                                      placeholder="Sheet URL (optional)"
                                      value={charSheetUrlInput}
                                      onChange={(e) => setCharSheetUrlInput(e.target.value)}
                                      className="w-full rounded bg-gray-700 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                    />
                                    <textarea
                                      placeholder="Character notes (optional)"
                                      value={charSheetNotesInput}
                                      onChange={(e) => setCharSheetNotesInput(e.target.value)}
                                      rows={2}
                                      className="w-full rounded bg-gray-700 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
                                    />
                                    <div className="flex gap-2">
                                      <button type="submit" disabled={savingCharName} className="text-xs text-indigo-400 hover:text-indigo-300 transition">
                                        {savingCharName ? "Saving…" : "Save"}
                                      </button>
                                      <button type="button" onClick={() => setEditingCharName(false)} className="text-xs text-gray-500 hover:text-gray-300 transition">
                                        Cancel
                                      </button>
                                    </div>
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
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                /* ── Edit form ─────────────────────────────────────────── */
                <form onSubmit={handleSave} className="p-5 space-y-3">
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
                    onChange={(e) => setEditForm((f) => ({ ...f, discord_webhook_url: e.target.value }))}
                    className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <div>
                    <input
                      type="text"
                      placeholder="Discord Server ID / Guild ID (optional)"
                      value={editForm.guild_id}
                      onChange={(e) => setEditForm((f) => ({ ...f, guild_id: e.target.value || "" }))}
                      className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <p className="mt-1 text-xs text-gray-500">Enable bot notifications. Leave blank to use webhook only.</p>
                  </div>
                  <input
                    type="text"
                    placeholder="Bot notification channel ID (optional)"
                    value={editForm.notification_channel_id}
                    onChange={(e) => setEditForm((f) => ({ ...f, notification_channel_id: e.target.value || "" }))}
                    className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />

                  {/* Invite code management (inside edit) */}
                  {campaign.invite_code && (
                    <div className="rounded-lg bg-gray-800/60 border border-gray-700 px-3 py-2">
                      <p className="text-xs text-gray-400 mb-1.5">Invite code</p>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 font-mono text-xs tracking-widest text-gray-300 truncate">
                          {campaign.invite_code}
                        </code>
                        <button type="button" onClick={handleCopyCode} className="text-xs text-gray-400 hover:text-white transition shrink-0">
                          {copied ? "Copied!" : "Copy"}
                        </button>
                        <button type="button" onClick={handleRegenerate} className="text-xs text-gray-500 hover:text-red-400 transition shrink-0">
                          Regenerate
                        </button>
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Campaign timezone</label>
                    <select
                      value={editForm.timezone}
                      onChange={(e) => setEditForm((f) => ({ ...f, timezone: e.target.value }))}
                      className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">— Use server default —</option>
                      {COMMON_TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Reminders (up to 3)</label>
                    <div className="space-y-2">
                      {editForm.reminders.map((r, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <input
                            type="number" min="1"
                            value={r.value}
                            onChange={(e) => setEditForm((f) => { const rows = [...f.reminders]; rows[i] = { ...rows[i], value: e.target.value }; return { ...f, reminders: rows }; })}
                            className="w-20 rounded-lg bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                          <select
                            value={r.unit}
                            onChange={(e) => setEditForm((f) => { const rows = [...f.reminders]; rows[i] = { ...rows[i], unit: e.target.value }; return { ...f, reminders: rows }; })}
                            className="rounded-lg bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          >
                            {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
                          </select>
                          <span className="text-xs text-gray-500">before session</span>
                          <button type="button" onClick={() => setEditForm((f) => ({ ...f, reminders: f.reminders.filter((_, j) => j !== i) }))} className="text-gray-600 hover:text-red-400 text-sm transition">✕</button>
                        </div>
                      ))}
                      {editForm.reminders.length < 3 && (
                        <button type="button" onClick={() => setEditForm((f) => ({ ...f, reminders: [...f.reminders, { value: 1, unit: "hours" }] }))} className="text-xs text-indigo-400 hover:text-indigo-300 transition">
                          + Add reminder
                        </button>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Vote notifications</label>
                    <div className="flex flex-wrap gap-2">
                      {[{ value: "", label: "Disabled" }, { value: "each_vote", label: "On each vote" }, { value: "all_voted", label: "When all voted" }].map((opt) => (
                        <button key={opt.value} type="button"
                          onClick={() => setEditForm((f) => ({ ...f, vote_notification_mode: opt.value }))}
                          className={`rounded-lg px-3 py-1.5 text-xs transition ${editForm.vote_notification_mode === opt.value ? "bg-indigo-600 text-white" : "border border-gray-700 text-gray-400 hover:border-gray-500"}`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Auto-close voting after (hours, blank = never)</label>
                    <input
                      type="number" min="1" placeholder="e.g. 72"
                      value={editForm.vote_auto_close_hours}
                      onChange={(e) => setEditForm((f) => ({ ...f, vote_auto_close_hours: e.target.value }))}
                      className="w-28 rounded-lg bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div className="flex items-start gap-3 pt-1">
                    <input
                      id="recap_email_enabled" type="checkbox"
                      checked={editForm.recap_email_enabled}
                      onChange={(e) => setEditForm((f) => ({ ...f, recap_email_enabled: e.target.checked }))}
                      className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-800 text-indigo-500 focus:ring-indigo-500"
                    />
                    <div>
                      <label htmlFor="recap_email_enabled" className="text-sm text-gray-300 cursor-pointer">Send post-session recap emails</label>
                      <p className="text-xs text-gray-500 mt-0.5">Emails attendees a summary when the bot uploads a transcript (requires user opt-in in profile).</p>
                    </div>
                  </div>
                  {editError && <p className="text-sm text-red-400">{editError}</p>}
                  <div className="flex gap-2 justify-end">
                    <button type="button" onClick={() => setEditing(false)} className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition">Cancel</button>
                    <button type="submit" disabled={saving} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition">
                      {saving ? "Saving…" : "Save"}
                    </button>
                  </div>
                </form>
              )}
            </section>

            {/* ── Panel 2: Sessions (tabbed) ─────────────────────────────────── */}
            <section className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
              {/* Tab bar + new session button */}
              <div className="flex items-center justify-between border-b border-gray-800 px-4">
                <div className="flex">
                  <TabBtn active={sessionTab === "upcoming"} onClick={() => setSessionTab("upcoming")}>
                    Upcoming ({upcomingSessions.length})
                  </TabBtn>
                  <TabBtn active={sessionTab === "completed"} onClick={() => setSessionTab("completed")}>
                    Completed ({completedSessions.length})
                  </TabBtn>
                  {isGm && (
                    <TabBtn active={sessionTab === "cancelled"} onClick={() => setSessionTab("cancelled")}>
                      Cancelled ({cancelledSessions.length})
                    </TabBtn>
                  )}
                </div>
                {isGm && (
                  <button
                    onClick={() => { setShowNewSession((v) => !v); setSessionTab("upcoming"); }}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 transition my-2"
                  >
                    {showNewSession ? "Cancel" : "+ New Session"}
                  </button>
                )}
              </div>

              <div className="p-4 space-y-3">
                {/* New-session form */}
                {showNewSession && sessionTab === "upcoming" && (
                  <form onSubmit={handleCreateSession} className="rounded-xl border border-gray-700 bg-gray-800/50 p-4 space-y-3">
                    <h4 className="font-medium text-sm">New Session</h4>
                    <input
                      placeholder="Title (optional)"
                      value={sessionForm.title}
                      onChange={(e) => setSessionForm((f) => ({ ...f, title: e.target.value }))}
                      className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <textarea
                      placeholder="Description (optional)"
                      rows={2}
                      value={sessionForm.description}
                      onChange={(e) => setSessionForm((f) => ({ ...f, description: e.target.value }))}
                      className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                    />
                    <div>
                      <label className="text-xs text-gray-400 mb-1.5 block">Scheduling mode</label>
                      <div className="flex flex-wrap gap-2">
                        {[{ value: "vote", label: "Vote (2–5 slots)" }, { value: "direct", label: "Direct" }, { value: "tentative", label: "Tentative" }].map((opt) => (
                          <button
                            key={opt.value} type="button"
                            onClick={() => setSessionForm((f) => ({ ...f, scheduling_mode: opt.value, times: opt.value === "vote" ? ["", ""] : [""] }))}
                            className={`rounded-lg px-3 py-1.5 text-xs transition ${sessionForm.scheduling_mode === opt.value ? "bg-indigo-600 text-white" : "border border-gray-700 text-gray-400 hover:border-gray-500"}`}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs text-gray-400 block">
                        {sessionForm.scheduling_mode === "vote" ? "Proposed times" : "Session time"}
                      </label>
                      {sessionForm.times.slice(0, sessionTimeCount).map((t, idx) => (
                        <div key={idx} className="flex items-center gap-2 flex-wrap">
                          <DateTimePicker value={t} onChange={(v) => setTime(idx, v)} />
                          {sessionForm.scheduling_mode === "vote" && sessionForm.times.length > 2 && (
                            <button type="button" onClick={() => removeTimeSlot(idx)} className="text-gray-600 hover:text-red-400 text-xs transition">✕</button>
                          )}
                        </div>
                      ))}
                      {sessionForm.scheduling_mode === "vote" && sessionForm.times.length < 5 && (
                        <button type="button" onClick={addTimeSlot} className="text-xs text-indigo-400 hover:text-indigo-300 transition">+ Add time slot</button>
                      )}
                    </div>
                    {sessionError && <p className="text-sm text-red-400">{sessionError}</p>}
                    <div className="flex gap-2 justify-end">
                      <button type="button" onClick={() => { setShowNewSession(false); setSessionForm({ title: "", description: "", scheduling_mode: "vote", times: ["", ""] }); setSessionError(null); }} className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition">Cancel</button>
                      <button type="submit" disabled={creatingSession} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition">
                        {creatingSession ? "Creating…" : "Create Session"}
                      </button>
                    </div>
                  </form>
                )}

                {/* Session list */}
                {(() => {
                  const list = sessionTab === "upcoming" ? upcomingSessions
                    : sessionTab === "completed" ? completedSessions
                    : cancelledSessions;
                  if (list.length === 0 && !showNewSession) {
                    return (
                      <p className="text-sm text-gray-600 py-4 text-center">
                        {sessionTab === "upcoming"
                          ? isGm ? "No upcoming sessions. Create one above." : "No upcoming sessions."
                          : sessionTab === "completed" ? "No completed sessions yet."
                          : "No cancelled sessions."}
                      </p>
                    );
                  }
                  return (
                    <ul className="space-y-2">
                      {list.map((s) => (
                        <li key={s.id} className="flex items-center gap-2">
                          <Link
                            to={`/sessions/${s.id}`}
                            className="flex-1 flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900 px-4 py-3 hover:border-gray-700 transition min-w-0"
                          >
                            <div className="min-w-0">
                              <p className="font-medium text-sm truncate">{s.title ?? "Untitled Session"}</p>
                              {s.confirmed_time ? (
                                <p className="text-xs text-gray-400 mt-0.5">{fmt(s.confirmed_time)}</p>
                              ) : (
                                <p className="text-xs text-gray-500 mt-0.5">{MODE_LABELS[s.scheduling_mode] ?? s.scheduling_mode}</p>
                              )}
                            </div>
                            <span className={`ml-3 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[s.status] ?? "bg-gray-800 text-gray-400"}`}>
                              {s.status}
                            </span>
                          </Link>
                          {sessionTab === "cancelled" && isGm && (
                            <button
                              onClick={() => reuseAsNewSession(s)}
                              title="Pre-fill a new session with this session's title and description"
                              className="shrink-0 rounded-lg border border-gray-700 px-2.5 py-1.5 text-xs text-gray-400 hover:border-indigo-600 hover:text-indigo-400 transition"
                            >
                              Reuse
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  );
                })()}
              </div>
            </section>

            {/* ── Panel 3: Journal | Wiki (tabbed) ──────────────────────────── */}
            <section className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
              <div className="flex items-center justify-between border-b border-gray-800 px-4">
                <div className="flex">
                  <TabBtn active={contentTab === "journal"} onClick={() => setContentTab("journal")}>
                    Campaign Journal
                  </TabBtn>
                  <TabBtn active={contentTab === "wiki"} onClick={() => setContentTab("wiki")}>
                    Wiki
                  </TabBtn>
                </div>
                {contentTab === "wiki" && isGm && (
                  <button
                    onClick={() => { setShowCreateLore(true); setEditingLoreId(null); }}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 transition my-2"
                  >
                    + New entry
                  </button>
                )}
              </div>

              <div className="p-4">
                {/* ── Journal tab ── */}
                {contentTab === "journal" && (
                  notes.length === 0 ? (
                    <div className="py-6 text-center">
                      <p className="text-sm text-gray-500">No notes written yet.</p>
                      <p className="text-xs text-gray-600 mt-1">Write notes on individual sessions to build your journal.</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {notes.map((entry) => (
                        <article key={entry.session_id} className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                          <div className="mb-3">
                            <Link to={`/sessions/${entry.session_id}`} className="font-medium text-sm hover:text-indigo-400 transition">
                              {entry.session_title ?? "Untitled Session"}
                            </Link>
                            {entry.confirmed_time && (
                              <p className="text-xs text-gray-500 mt-0.5">{fmtDate(entry.confirmed_time)}</p>
                            )}
                          </div>
                          {entry.my_notes?.length > 0 && (
                            <div className="mb-3 space-y-2">
                              <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">My Notes</p>
                              {entry.my_notes.map((note, i) => (
                                <p key={i} className="text-sm text-gray-300 whitespace-pre-wrap">{note}</p>
                              ))}
                            </div>
                          )}
                          {entry.gm_public_note && (
                            <div className={entry.my_notes?.length > 0 ? "mt-3 pt-3 border-t border-gray-800" : ""}>
                              <p className="text-xs text-amber-500 font-medium uppercase tracking-wide mb-1">GM Notes</p>
                              <p className="text-sm text-gray-300 whitespace-pre-wrap">{entry.gm_public_note}</p>
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  )
                )}

                {/* ── Wiki tab ── */}
                {contentTab === "wiki" && (
                  <div className="space-y-4">
                    {/* Create form */}
                    {isGm && showCreateLore && (
                      <form onSubmit={handleCreateLore} className="rounded-xl border border-indigo-800 bg-gray-800/50 p-4 space-y-3">
                        <div className="flex gap-3">
                          <div className="flex-1">
                            <label className="block text-xs text-gray-400 mb-1">Type</label>
                            <select
                              value={loreCreateForm.entry_type}
                              onChange={(e) => setLoreCreateForm((f) => ({ ...f, entry_type: e.target.value }))}
                              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm"
                            >
                              {LORE_TYPES.map((t) => <option key={t} value={t}>{LORE_TYPE_LABELS[t]}</option>)}
                            </select>
                          </div>
                          <div className="flex-[3]">
                            <label className="block text-xs text-gray-400 mb-1">Title</label>
                            <input
                              required
                              value={loreCreateForm.title}
                              onChange={(e) => setLoreCreateForm((f) => ({ ...f, title: e.target.value }))}
                              placeholder="Entry title"
                              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-400 mb-1">Body</label>
                          <textarea
                            required rows={4}
                            value={loreCreateForm.body}
                            onChange={(e) => setLoreCreateForm((f) => ({ ...f, body: e.target.value }))}
                            placeholder="Describe this entry…"
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm resize-y"
                          />
                        </div>
                        {loreCreateError && <p className="text-xs text-red-400">{loreCreateError}</p>}
                        <div className="flex gap-2 justify-end">
                          <button type="button" onClick={() => { setShowCreateLore(false); setLoreCreateForm(BLANK_LORE); }} className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-800 transition">Cancel</button>
                          <button type="submit" disabled={creatingLore} className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-3 py-1.5 text-sm font-medium transition">
                            {creatingLore ? "Creating…" : "Create"}
                          </button>
                        </div>
                      </form>
                    )}

                    {/* Type filter pills */}
                    {loreEntries.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {["all", ...LORE_TYPES].map((t) => (
                          <button
                            key={t}
                            onClick={() => setLoreTypeFilter(t)}
                            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition ${
                              loreTypeFilter === t
                                ? "border-indigo-600 bg-indigo-600 text-white"
                                : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
                            }`}
                          >
                            {t === "all" ? `All (${loreEntries.length})` : `${LORE_TYPE_LABELS[t]} (${loreEntries.filter((e) => e.entry_type === t).length})`}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Entry list */}
                    {filteredLore.length === 0 && !showCreateLore && (
                      <p className="text-sm text-gray-500 py-4 text-center">
                        {loreEntries.length === 0
                          ? isGm ? "No lore entries yet. Use \"+ New entry\" to add the first one." : "No lore entries yet."
                          : "No entries in this category."}
                      </p>
                    )}
                    <div className="space-y-2">
                      {filteredLore.map((entry) => (
                        <div key={entry.id} className="rounded-xl border border-gray-800 overflow-hidden">
                          {editingLoreId === entry.id ? (
                            <form onSubmit={handleSaveLore} className="p-4 space-y-3">
                              <div className="flex gap-3">
                                <select
                                  value={loreEditForm.entry_type}
                                  onChange={(e) => setLoreEditForm((f) => ({ ...f, entry_type: e.target.value }))}
                                  className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm"
                                >
                                  {LORE_TYPES.map((t) => <option key={t} value={t}>{LORE_TYPE_LABELS[t]}</option>)}
                                </select>
                                <input
                                  required
                                  value={loreEditForm.title}
                                  onChange={(e) => setLoreEditForm((f) => ({ ...f, title: e.target.value }))}
                                  className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm"
                                />
                              </div>
                              <textarea
                                required rows={4}
                                value={loreEditForm.body}
                                onChange={(e) => setLoreEditForm((f) => ({ ...f, body: e.target.value }))}
                                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm resize-y"
                              />
                              {loreEditError && <p className="text-xs text-red-400">{loreEditError}</p>}
                              <div className="flex gap-2 justify-end">
                                <button type="button" onClick={() => setEditingLoreId(null)} className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-800 transition">Cancel</button>
                                <button type="submit" disabled={savingLore} className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-3 py-1.5 text-sm font-medium transition">
                                  {savingLore ? "Saving…" : "Save"}
                                </button>
                              </div>
                            </form>
                          ) : (
                            <>
                              <button
                                onClick={() => toggleLoreExpand(entry.id)}
                                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-800/40 transition"
                              >
                                <LoreTypeBadge type={entry.entry_type} />
                                <span className="flex-1 text-sm font-medium">{entry.title}</span>
                                <span className="text-gray-600 text-xs">{expandedLoreIds.has(entry.id) ? "▲" : "▼"}</span>
                              </button>
                              {expandedLoreIds.has(entry.id) && (
                                <div className="border-t border-gray-800 px-4 pb-4 pt-3">
                                  <p className="text-sm text-gray-300 whitespace-pre-wrap">{entry.body}</p>
                                  {isGm && (
                                    <div className="flex gap-3 mt-3">
                                      <button onClick={() => { setEditingLoreId(entry.id); setLoreEditForm({ entry_type: entry.entry_type, title: entry.title, body: entry.body }); }} className="text-xs text-indigo-400 hover:text-indigo-300 transition">Edit</button>
                                      <button onClick={() => handleDeleteLore(entry.id)} className="text-xs text-red-500 hover:text-red-400 transition">Delete</button>
                                    </div>
                                  )}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>

          </div>
          {/* ══ END LEFT COLUMN ══════════════════════════════════════════════ */}

          {/* ══ RIGHT COLUMN: Milestones timeline ════════════════════════════ */}
          <div className="space-y-3 lg:sticky lg:top-6">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">Milestones</h3>
              {isGm && !showNewMilestone && (
                <button
                  onClick={() => setShowNewMilestone(true)}
                  className="rounded-lg border border-gray-700 px-3 py-1 text-xs hover:border-gray-500 transition"
                >
                  + Add
                </button>
              )}
            </div>

            {milestoneError && <p className="text-sm text-red-400">{milestoneError}</p>}

            {showNewMilestone && isGm && (
              <form
                onSubmit={handleCreateMilestone}
                className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-3"
              >
                <h4 className="font-medium text-sm">New Milestone</h4>
                <input
                  required
                  placeholder="Title"
                  value={milestoneForm.title}
                  onChange={(e) => setMilestoneForm((f) => ({ ...f, title: e.target.value }))}
                  className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <textarea
                  placeholder="Description (optional)"
                  rows={2}
                  value={milestoneForm.description}
                  onChange={(e) => setMilestoneForm((f) => ({ ...f, description: e.target.value }))}
                  className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Linked session</label>
                    <select
                      value={milestoneForm.session_id}
                      onChange={(e) => setMilestoneForm((f) => ({ ...f, session_id: e.target.value }))}
                      className="w-full rounded-lg bg-gray-800 px-2 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">— None —</option>
                      {sessions.map((s) => <option key={s.id} value={s.id}>{s.title ?? "Untitled Session"}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Date</label>
                    <input
                      type="date"
                      value={milestoneForm.milestone_date}
                      onChange={(e) => setMilestoneForm((f) => ({ ...f, milestone_date: e.target.value }))}
                      className="w-full rounded-lg bg-gray-800 px-2 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button type="button" onClick={() => { setShowNewMilestone(false); setMilestoneForm({ title: "", description: "", session_id: "", milestone_date: "" }); }} className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs hover:border-gray-500 transition">Cancel</button>
                  <button type="submit" disabled={savingMilestone} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50 transition">
                    {savingMilestone ? "Adding…" : "Add"}
                  </button>
                </div>
              </form>
            )}

            {milestones.length === 0 && !showNewMilestone && (
              <p className="text-sm text-gray-600 text-center py-4">
                {isGm ? "No milestones yet. Add one to track key events." : "No milestones yet."}
              </p>
            )}

            {/* Timeline */}
            {milestones.length > 0 && (
              <div className="relative">
                {/* Vertical connecting line */}
                <div className="absolute left-3 top-4 bottom-4 w-px bg-gray-800" />

                <div className="space-y-0">
                  {milestones.map((m) =>
                    editingMilestone === m.id ? (
                      <form
                        key={m.id}
                        onSubmit={(e) => handleUpdateMilestone(e, m.id)}
                        className="relative mb-3 ml-9 rounded-xl border border-indigo-900/50 bg-gray-900 p-3 space-y-2"
                      >
                        <input
                          required
                          value={editMilestoneForm.title}
                          onChange={(e) => setEditMilestoneForm((f) => ({ ...f, title: e.target.value }))}
                          className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                        <textarea
                          placeholder="Description (optional)"
                          rows={2}
                          value={editMilestoneForm.description ?? ""}
                          onChange={(e) => setEditMilestoneForm((f) => ({ ...f, description: e.target.value }))}
                          className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <select
                            value={editMilestoneForm.session_id ?? ""}
                            onChange={(e) => setEditMilestoneForm((f) => ({ ...f, session_id: e.target.value }))}
                            className="w-full rounded-lg bg-gray-800 px-2 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          >
                            <option value="">— No session —</option>
                            {sessions.map((s) => <option key={s.id} value={s.id}>{s.title ?? "Untitled"}</option>)}
                          </select>
                          <input
                            type="date"
                            value={editMilestoneForm.milestone_date ?? ""}
                            onChange={(e) => setEditMilestoneForm((f) => ({ ...f, milestone_date: e.target.value }))}
                            className="w-full rounded-lg bg-gray-800 px-2 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                        <div className="flex gap-2 justify-end">
                          <button type="button" onClick={() => setEditingMilestone(null)} className="rounded-lg border border-gray-700 px-2.5 py-1 text-xs hover:border-gray-500 transition">Cancel</button>
                          <button type="submit" disabled={savingMilestone} className="rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50 transition">
                            {savingMilestone ? "Saving…" : "Save"}
                          </button>
                        </div>
                      </form>
                    ) : (
                      <div key={m.id} className="relative flex gap-3 pb-5 group">
                        {/* Timeline node */}
                        <div className="relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-gray-700 bg-gray-950 text-xs text-gray-500">
                          ◆
                        </div>
                        {/* Content */}
                        <div className="flex-1 min-w-0 pt-0.5">
                          <p className="font-medium text-sm leading-snug">{m.title}</p>
                          {m.description && (
                            <p className="text-xs text-gray-400 mt-0.5 whitespace-pre-wrap">{m.description}</p>
                          )}
                          <div className="flex items-center gap-3 mt-1">
                            {m.milestone_date && (
                              <span className="text-xs text-gray-600">{fmtDate(m.milestone_date)}</span>
                            )}
                            {m.session_id && (() => {
                              const linkedSession = sessions.find((s) => s.id === m.session_id);
                              return linkedSession ? (
                                <Link to={`/sessions/${m.session_id}`} className="text-xs text-indigo-400 hover:text-indigo-300 transition">
                                  {linkedSession.title ?? "Untitled Session"} ↗
                                </Link>
                              ) : null;
                            })()}
                          </div>
                          {isGm && (
                            <div className="flex gap-3 mt-1 opacity-0 group-hover:opacity-100 transition">
                              <button
                                onClick={() => {
                                  setEditingMilestone(m.id);
                                  setEditMilestoneForm({
                                    title: m.title,
                                    description: m.description ?? "",
                                    session_id: m.session_id ?? "",
                                    milestone_date: m.milestone_date ? new Date(m.milestone_date).toISOString().slice(0, 10) : "",
                                  });
                                }}
                                className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                              >
                                Edit
                              </button>
                              <button onClick={() => handleDeleteMilestone(m.id)} className="text-xs text-red-400 hover:text-red-300 transition">Delete</button>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </div>
          {/* ══ END RIGHT COLUMN ═════════════════════════════════════════════ */}

        </div>
      </main>
    </div>
  );
}
