/**
 * CampaignLore — campaign wiki / lore entries page.
 * GM can create, edit, and delete entries.  All members can read.
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import NavBar from "../components/NavBar.jsx";
import {
  fetchCampaign,
  fetchMembers,
  fetchLoreEntries,
  createLoreEntry,
  updateLoreEntry,
  deleteLoreEntry,
} from "../api/campaigns.js";

const LORE_TYPES = ["location", "faction", "npc", "item", "event", "other"];

const TYPE_LABELS = {
  location: "Location",
  faction: "Faction",
  npc: "NPC",
  item: "Item",
  event: "Event",
  other: "Other",
};

const TYPE_COLOURS = {
  location: "text-emerald-400 bg-emerald-950 border-emerald-800",
  faction: "text-violet-400 bg-violet-950 border-violet-800",
  npc: "text-sky-400 bg-sky-950 border-sky-800",
  item: "text-amber-400 bg-amber-950 border-amber-800",
  event: "text-rose-400 bg-rose-950 border-rose-800",
  other: "text-gray-400 bg-gray-900 border-gray-700",
};

function TypeBadge({ type }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${TYPE_COLOURS[type] ?? TYPE_COLOURS.other}`}
    >
      {TYPE_LABELS[type] ?? type}
    </span>
  );
}

const BLANK_FORM = { entry_type: "location", title: "", body: "", linked_session_id: "" };

export default function CampaignLore() {
  const { id: campaignId } = useParams();
  const { user } = useAuth();

  const [campaign, setCampaign] = useState(null);
  const [entries, setEntries] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // filter
  const [activeType, setActiveType] = useState("all");

  // create form
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState(BLANK_FORM);
  const [createError, setCreateError] = useState(null);
  const [creating, setCreating] = useState(false);

  // edit form
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(BLANK_FORM);
  const [editError, setEditError] = useState(null);
  const [saving, setSaving] = useState(false);

  // expanded entries
  const [expandedIds, setExpandedIds] = useState(new Set());

  useEffect(() => {
    Promise.all([
      fetchCampaign(campaignId),
      fetchLoreEntries(campaignId),
      fetchMembers(campaignId),
    ])
      .then(([c, e, m]) => {
        setCampaign(c);
        setEntries(e);
        setMembers(m);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [campaignId]);

  const isGm = members.some((m) => m.user_id === user?.id && m.role === "gm");

  const filtered =
    activeType === "all" ? entries : entries.filter((e) => e.entry_type === activeType);

  function toggleExpand(id) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleCreate(e) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const payload = {
        entry_type: createForm.entry_type,
        title: createForm.title.trim(),
        body: createForm.body.trim(),
        linked_session_id: createForm.linked_session_id || null,
      };
      const created = await createLoreEntry(campaignId, payload);
      setEntries((prev) =>
        [...prev, created].sort((a, b) =>
          a.entry_type.localeCompare(b.entry_type) || a.title.localeCompare(b.title)
        )
      );
      setShowCreate(false);
      setCreateForm(BLANK_FORM);
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  }

  function startEdit(entry) {
    setEditingId(entry.id);
    setEditForm({
      entry_type: entry.entry_type,
      title: entry.title,
      body: entry.body,
      linked_session_id: entry.linked_session_id ?? "",
    });
    setEditError(null);
  }

  async function handleSave(e) {
    e.preventDefault();
    setEditError(null);
    setSaving(true);
    try {
      const payload = {
        entry_type: editForm.entry_type,
        title: editForm.title.trim(),
        body: editForm.body.trim(),
        linked_session_id: editForm.linked_session_id || null,
      };
      const updated = await updateLoreEntry(campaignId, editingId, payload);
      setEntries((prev) =>
        prev
          .map((en) => (en.id === editingId ? updated : en))
          .sort((a, b) =>
            a.entry_type.localeCompare(b.entry_type) || a.title.localeCompare(b.title)
          )
      );
      setEditingId(null);
    } catch (err) {
      setEditError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this lore entry? This cannot be undone.")) return;
    try {
      await deleteLoreEntry(campaignId, id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
      if (editingId === id) setEditingId(null);
    } catch (err) {
      alert(err.message);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-white flex items-center justify-center">
        <p className="text-gray-500">Loading wiki…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-white flex items-center justify-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-white">
      <header className="border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to={`/campaigns/${campaignId}`}
            className="text-gray-500 hover:text-gray-900 dark:hover:text-white transition text-sm"
          >
            ← {campaign?.name ?? "Campaign"}
          </Link>
          <span className="text-gray-400 dark:text-gray-700">/</span>
          <span className="font-semibold">Wiki</span>
        </div>
        <div className="flex items-center gap-3">
        {isGm && (
          <button
            onClick={() => { setShowCreate(true); setEditingId(null); }}
            className="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-sm font-medium transition"
          >
            + New entry
          </button>
        )}
        <NavBar />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 space-y-6">

        {/* Create form */}
        {isGm && showCreate && (
          <div className="rounded-xl border border-indigo-800 bg-gray-50 dark:bg-gray-900 p-5">
            <h2 className="font-semibold mb-4">New lore entry</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Type</label>
                  <select
                    value={createForm.entry_type}
                    onChange={(e) => setCreateForm((f) => ({ ...f, entry_type: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm"
                  >
                    {LORE_TYPES.map((t) => (
                      <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                    ))}
                  </select>
                </div>
                <div className="flex-[3]">
                  <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Title</label>
                  <input
                    type="text"
                    required
                    value={createForm.title}
                    onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm"
                    placeholder="Entry title"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Body</label>
                <textarea
                  required
                  rows={5}
                  value={createForm.body}
                  onChange={(e) => setCreateForm((f) => ({ ...f, body: e.target.value }))}
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm resize-y"
                  placeholder="Describe this entry…"
                />
              </div>
              {createError && <p className="text-xs text-red-400">{createError}</p>}
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => { setShowCreate(false); setCreateForm(BLANK_FORM); }}
                  className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-3 py-1.5 text-sm font-medium transition"
                >
                  {creating ? "Creating…" : "Create"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Type filter */}
        <div className="flex flex-wrap gap-2">
          {["all", ...LORE_TYPES].map((t) => (
            <button
              key={t}
              onClick={() => setActiveType(t)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                activeType === t
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-gray-400 dark:hover:border-gray-500 hover:text-gray-900 dark:hover:text-white"
              }`}
            >
              {t === "all" ? "All" : TYPE_LABELS[t]}
              {t !== "all" && (
                <span className="ml-1 text-gray-500 dark:text-gray-500">
                  ({entries.filter((e) => e.entry_type === t).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Entry list */}
        {filtered.length === 0 ? (
          <p className="text-sm text-gray-500">
            {entries.length === 0
              ? isGm
                ? "No lore entries yet. Use \"+ New entry\" to add the first one."
                : "No lore entries yet."
              : "No entries in this category."}
          </p>
        ) : (
          <div className="space-y-3">
            {filtered.map((entry) => (
              <div
                key={entry.id}
                className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 overflow-hidden"
              >
                {editingId === entry.id ? (
                  /* ── Edit form ── */
                  <form onSubmit={handleSave} className="p-5 space-y-3">
                    <div className="flex gap-3">
                      <div className="flex-1">
                        <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Type</label>
                        <select
                          value={editForm.entry_type}
                          onChange={(e) => setEditForm((f) => ({ ...f, entry_type: e.target.value }))}
                          className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm"
                        >
                          {LORE_TYPES.map((t) => (
                            <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                          ))}
                        </select>
                      </div>
                      <div className="flex-[3]">
                        <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Title</label>
                        <input
                          type="text"
                          required
                          value={editForm.title}
                          onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                          className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Body</label>
                      <textarea
                        required
                        rows={5}
                        value={editForm.body}
                        onChange={(e) => setEditForm((f) => ({ ...f, body: e.target.value }))}
                        className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm resize-y"
                      />
                    </div>
                    {editError && <p className="text-xs text-red-400">{editError}</p>}
                    <div className="flex gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={saving}
                        className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-3 py-1.5 text-sm font-medium transition"
                      >
                        {saving ? "Saving…" : "Save"}
                      </button>
                    </div>
                  </form>
                ) : (
                  /* ── Read view ── */
                  <>
                    <button
                      onClick={() => toggleExpand(entry.id)}
                      className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-gray-200/40 dark:hover:bg-gray-800/40 transition"
                    >
                      <TypeBadge type={entry.entry_type} />
                      <span className="flex-1 font-medium">{entry.title}</span>
                      <span className="text-gray-500 dark:text-gray-600 text-sm">
                        {expandedIds.has(entry.id) ? "▲" : "▼"}
                      </span>
                    </button>

                    {expandedIds.has(entry.id) && (
                      <div className="border-t border-gray-200 dark:border-gray-800 px-5 pb-5 pt-4">
                        <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{entry.body}</p>
                        {isGm && (
                          <div className="flex gap-3 mt-4">
                            <button
                              onClick={() => startEdit(entry)}
                              className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDelete(entry.id)}
                              className="text-xs text-red-500 hover:text-red-400 transition"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
