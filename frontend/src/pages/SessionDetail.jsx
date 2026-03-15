/**
 * SessionDetail — detail page for a single game session.
 *
 * Displays session status, proposed time slots, and (for vote-mode proposed
 * sessions) an interactive VotingGrid where players register availability.
 *
 * GMs see additional controls:
 *   - Confirm tentative sessions (no slot selection needed)
 *   - Confirm vote-mode sessions by clicking "Confirm this slot" on the winner
 *   - Cancel any proposed session
 *   - Add/edit post-session notes
 *
 * Data is loaded sequentially: session first, then members + votes in parallel
 * (because the member list requires the campaign_id from the session).
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import { fetchMembers } from "../api/campaigns.js";
import {
  cancelSession,
  confirmSession,
  fetchAttendance,
  fetchMyNotes,
  fetchSession,
  fetchVotes,
  setAttendance,
  updateSession,
  upsertMyNote,
} from "../api/sessions.js";
import DateTimePicker from "../components/DateTimePicker.jsx";
import VotingGrid from "../components/VotingGrid.jsx";

const MODE_LABELS = { vote: "Vote", direct: "Direct", tentative: "Tentative" };
const STATUS_CLASSES = {
  proposed:  "bg-blue-900/50 text-blue-300",
  confirmed: "bg-green-900/50 text-green-300",
  completed: "bg-gray-800 text-gray-400",
  cancelled: "bg-red-900/40 text-red-400",
};

function fmt(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Format a Date as YYYYMMDDTHHMMSSZ for Google Calendar URLs. */
function fmtGcal(date) {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function googleCalendarUrl(session) {
  const start = new Date(session.confirmed_time);
  const end = new Date(start.getTime() + 4 * 60 * 60 * 1000); // +4h default
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: session.title || "Game Session",
    dates: `${fmtGcal(start)}/${fmtGcal(end)}`,
    details: session.description || "",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function RecordingSection({ session }) {
  const [transcriptOpen, setTranscriptOpen] = useState(false);

  return (
    <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-400">Recording & Transcript</h3>
        {session.transcript_updated_at && (
          <span className="text-xs text-gray-600">
            Last updated:{" "}
            {new Date(session.transcript_updated_at).toLocaleString(undefined, {
              month: "short", day: "numeric", year: "numeric",
              hour: "2-digit", minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {session.recording_url && (
        <a
          href={session.recording_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 transition"
        >
          Listen to recording ↗
        </a>
      )}

      {session.summary && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Session Summary
          </p>
          <p className="text-sm text-gray-300 whitespace-pre-wrap">{session.summary}</p>
        </div>
      )}

      {session.transcript && (
        <div>
          <button
            onClick={() => setTranscriptOpen((o) => !o)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition"
          >
            <span>{transcriptOpen ? "▾" : "▸"}</span>
            {transcriptOpen ? "Hide full transcript" : "Show full transcript"}
          </button>
          {transcriptOpen && (
            <pre className="mt-3 text-xs text-gray-400 whitespace-pre-wrap font-mono bg-gray-800/60 rounded-lg p-4 overflow-x-auto">
              {session.transcript}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}


export default function SessionDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [members, setMembers] = useState([]);
  const [votes, setVotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // GM session-notes form (stored on the session object)
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);

  // GM inline-edit form (title / description)
  const [editingSession, setEditingSession] = useState(false);
  const [editForm, setEditForm] = useState({ title: "", description: "" });
  const [savingSession, setSavingSession] = useState(false);

  // Reschedule form (confirmed sessions only)
  const [editingTime, setEditingTime] = useState(false);
  const [rescheduleTime, setRescheduleTime] = useState("");
  const [savingTime, setSavingTime] = useState(false);

  // Per-user notes (one private, one public for GMs)
  const [myNotes, setMyNotes] = useState([]);
  const [editingPrivate, setEditingPrivate] = useState(false);
  const [privateInput, setPrivateInput] = useState("");
  const [savingPrivate, setSavingPrivate] = useState(false);
  const [editingPublic, setEditingPublic] = useState(false);
  const [publicInput, setPublicInput] = useState("");
  const [savingPublic, setSavingPublic] = useState(false);

  // Attendance (completed sessions, GM only)
  const [attendance, setAttendance] = useState([]);
  const [attendanceBusy, setAttendanceBusy] = useState(null); // user_id being updated

  const isGm = members.some((m) => m.user_id === user?.id && m.role === "gm");

  useEffect(() => {
    fetchSession(id)
      .then((s) => {
        setSession(s);
        setNotes(s.session_notes ?? "");
        setEditForm({ title: s.title ?? "", description: s.description ?? "" });
        return Promise.all([fetchMembers(s.campaign_id), fetchVotes(s.id), fetchMyNotes(s.id)]);
      })
      .then(([m, v, notes]) => {
        setMembers(m);
        setVotes(v);
        setMyNotes(notes ?? []);
        const priv = (notes ?? []).find((n) => n.visibility === "private");
        const pub = (notes ?? []).find((n) => n.visibility === "public");
        setPrivateInput(priv?.content ?? "");
        setPublicInput(pub?.content ?? "");
        return fetchAttendance(id).catch(() => []);
      })
      .then((att) => {
        setAttendance(att ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleConfirm = async (slotId = null) => {
    // slotId is null for tentative sessions; for vote-mode the GM passes the winning slot.
    setActionError(null);
    try {
      const updated = await confirmSession(id, slotId);
      setSession(updated);
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleCancel = async () => {
    if (!confirm("Cancel this session?")) return;
    setActionError(null);
    try {
      await cancelSession(id);
      navigate(`/campaigns/${session.campaign_id}`);
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleSaveNotes = async (e) => {
    e.preventDefault();
    setSavingNotes(true);
    try {
      const updated = await updateSession(id, { session_notes: notes });
      setSession(updated);
      setEditingNotes(false);
    } catch (e) {
      setActionError(e.message);
    } finally {
      setSavingNotes(false);
    }
  };

  const handleSaveSession = async (e) => {
    e.preventDefault();
    setSavingSession(true);
    try {
      const updated = await updateSession(id, {
        title: editForm.title || null,
        description: editForm.description || null,
      });
      setSession(updated);
      setEditingSession(false);
    } catch (e) {
      setActionError(e.message);
    } finally {
      setSavingSession(false);
    }
  };

  const handleReschedule = async (e) => {
    e.preventDefault();
    if (!rescheduleTime) return;
    setSavingTime(true);
    try {
      const updated = await updateSession(id, {
        reschedule_time: new Date(rescheduleTime).toISOString(),
      });
      setSession(updated);
      setEditingTime(false);
      setRescheduleTime("");
    } catch (e) {
      setActionError(e.message);
    } finally {
      setSavingTime(false);
    }
  };

  const handleSaveNote = async (visibility, content, setSaving, setEditing) => {
    setSaving(true);
    try {
      const saved = await upsertMyNote(id, content, visibility);
      setMyNotes((prev) => {
        const next = prev.filter((n) => n.visibility !== visibility);
        return [...next, saved];
      });
      setEditing(false);
    } catch (e) {
      setActionError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleAttendance = async (userId, currentAttended) => {
    setAttendanceBusy(userId);
    try {
      const updated = await setAttendance(id, userId, !currentAttended);
      setAttendance((prev) =>
        prev.map((a) => (a.user_id === userId ? { ...a, attended: updated.attended } : a))
      );
    } catch (e) {
      setActionError(e.message);
    } finally {
      setAttendanceBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-gray-950 gap-4">
        <p className="text-red-400">{error ?? "Session not found."}</p>
        <Link to="/dashboard" className="text-sm text-indigo-400 hover:underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  // Derived booleans used to control which UI sections and GM actions are visible
  const isProposed = session.status === "proposed";
  const isConfirmed = session.status === "confirmed";
  const isVote = session.scheduling_mode === "vote";
  const isTentative = session.scheduling_mode === "tentative";

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link
          to={`/campaigns/${session.campaign_id}`}
          className="text-gray-500 hover:text-white transition text-sm"
        >
          ← Campaign
        </Link>
        <span className="text-gray-700">/</span>
        <span className="font-semibold">{session.title ?? "Untitled Session"}</span>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 space-y-6">
        {actionError && (
          <p className="rounded-lg bg-red-900/40 border border-red-800 px-4 py-2 text-sm text-red-300">
            {actionError}
          </p>
        )}

        {/* Session header card */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          {editingSession ? (
            <form onSubmit={handleSaveSession} className="space-y-3">
              <input
                placeholder="Session title (optional)"
                value={editForm.title}
                onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <textarea
                placeholder="Description (optional)"
                rows={2}
                value={editForm.description}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setEditingSession(false)} className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition">Cancel</button>
                <button type="submit" disabled={savingSession} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition">{savingSession ? "Saving…" : "Save"}</button>
              </div>
            </form>
          ) : (
            <>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h2 className="text-xl font-bold">{session.title ?? "Untitled Session"}</h2>
                  {session.description && (
                    <p className="mt-2 text-sm text-gray-300">{session.description}</p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASSES[session.status]}`}>
                    {session.status.charAt(0).toUpperCase() + session.status.slice(1)}
                  </span>
                  <span className="rounded-full bg-gray-800 px-2.5 py-0.5 text-xs text-gray-400">
                    {MODE_LABELS[session.scheduling_mode]}
                  </span>
                </div>
              </div>

              {/* Confirmed time */}
              {session.confirmed_time && (
                <p className="mt-4 text-sm text-green-300 font-medium">
                  {isConfirmed ? "Confirmed:" : "Tentative:"} {fmt(session.confirmed_time)}
                </p>
              )}

              {/* Reschedule form (confirmed sessions) */}
              {isGm && isConfirmed && (
                <div className="mt-3">
                  {editingTime ? (
                    <form onSubmit={handleReschedule} className="flex items-center gap-2 flex-wrap">
                      <DateTimePicker
                        value={rescheduleTime}
                        onChange={setRescheduleTime}
                      />
                      <button type="submit" disabled={savingTime} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50 transition">{savingTime ? "…" : "Reschedule"}</button>
                      <button type="button" onClick={() => setEditingTime(false)} className="text-xs text-gray-500 hover:text-gray-300 transition">Cancel</button>
                    </form>
                  ) : (
                    <button onClick={() => setEditingTime(true)} className="text-xs text-indigo-400 hover:text-indigo-300 transition">Reschedule</button>
                  )}
                </div>
              )}

              {/* GM actions */}
              {isGm && (
                <div className="mt-4 flex gap-2 flex-wrap">
                  <button
                    onClick={() => setEditingSession(true)}
                    className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition"
                  >
                    Edit
                  </button>
                  {isProposed && isTentative && (
                    <button
                      onClick={() => handleConfirm(null)}
                      className="rounded-lg bg-green-700 px-3 py-1.5 text-sm font-medium hover:bg-green-600 transition"
                    >
                      Confirm Session
                    </button>
                  )}
                  {isProposed && (
                    <button
                      onClick={handleCancel}
                      className="rounded-lg border border-red-900 px-3 py-1.5 text-sm text-red-400 hover:border-red-700 transition"
                    >
                      Cancel Session
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </section>

        {/* Time slots */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h3 className="text-sm font-medium text-gray-400 mb-4">
            {isVote ? "Proposed Time Slots" : "Scheduled Time"}
          </h3>

          {session.time_slots.length === 0 ? (
            <p className="text-sm text-gray-600">No time slots yet.</p>
          ) : (
            <ul className="space-y-2">
              {session.time_slots.map((slot) => {
                const isWinner =
                  isConfirmed &&
                  session.confirmed_time &&
                  new Date(slot.proposed_time).getTime() ===
                    new Date(session.confirmed_time).getTime();

                return (
                  <li
                    key={slot.id}
                    className={`flex items-center justify-between rounded-lg px-4 py-3 ${
                      isWinner
                        ? "border border-green-800 bg-green-900/20"
                        : "bg-gray-800/60"
                    }`}
                  >
                    <span className="text-sm">{fmt(slot.proposed_time)}</span>
                    <div className="flex items-center gap-3">
                      {isWinner && (
                        <span className="text-xs text-green-400 font-medium">Confirmed</span>
                      )}
                      {/* Vote-mode confirmation: GM selects the winning slot */}
                      {isGm && isProposed && isVote && (
                        <button
                          onClick={() => handleConfirm(slot.id)}
                          className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                        >
                          Confirm this slot
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {/* Voting grid — vote-mode proposed sessions */}
          {isVote && isProposed && members.length > 0 && (
            <div className="mt-4 border-t border-gray-800 pt-4">
              <p className="text-xs text-gray-500 mb-3">
                Click your cell to vote &mdash; cycles Yes → Maybe → No → (clear)
              </p>
              <VotingGrid
                session={session}
                members={members}
                currentUser={user}
                initialVotes={votes}
              />
            </div>
          )}
        </section>

        {/* Calendar downloads — confirmed sessions only */}
        {isConfirmed && session.confirmed_time && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <h3 className="text-sm font-medium text-gray-400 mb-3">Add to Calendar</h3>
            <div className="flex flex-wrap gap-3">
              <a
                href={`/api/sessions/${id}/calendar.ics`}
                download
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:border-gray-500 hover:text-white transition"
              >
                Download .ics
              </a>
              <a
                href={`webcal://${window.location.host}/api/sessions/${id}/calendar.ics`}
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:border-gray-500 hover:text-white transition"
              >
                Apple Calendar
              </a>
              <a
                href={googleCalendarUrl(session)}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:border-gray-500 hover:text-white transition"
              >
                Google Calendar
              </a>
            </div>
          </section>
        )}

        {/* Session notes */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-400">Session Notes</h3>
            {isGm && !editingNotes && (
              <button
                onClick={() => setEditingNotes(true)}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition"
              >
                {session.session_notes ? "Edit" : "Add notes"}
              </button>
            )}
          </div>

          {editingNotes ? (
            <form onSubmit={handleSaveNotes} className="space-y-2">
              <textarea
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Post-session notes, recap, highlights…"
                className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setEditingNotes(false)}
                  className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs hover:border-gray-500 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingNotes}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
                >
                  {savingNotes ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          ) : session.session_notes ? (
            <p className="text-sm text-gray-300 whitespace-pre-wrap">{session.session_notes}</p>
          ) : (
            <p className="text-sm text-gray-600">No notes yet.</p>
          )}
        </section>

        {/* Per-user notes — private panel (all users) */}
        {(() => {
          const privateNote = myNotes.find((n) => n.visibility === "private");
          return (
            <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-400">My Notes
                  <span className="ml-2 text-xs rounded-full bg-gray-800 text-gray-500 px-2 py-0.5">Private</span>
                </h3>
                {!editingPrivate && (
                  <button
                    onClick={() => setEditingPrivate(true)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                  >
                    {privateNote ? "Edit" : "Add note"}
                  </button>
                )}
              </div>
              {editingPrivate ? (
                <form
                  onSubmit={(e) => { e.preventDefault(); handleSaveNote("private", privateInput, setSavingPrivate, setEditingPrivate); }}
                  className="space-y-2"
                >
                  <textarea
                    rows={4}
                    autoFocus
                    value={privateInput}
                    onChange={(e) => setPrivateInput(e.target.value)}
                    placeholder="Your private notes for this session…"
                    className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => { setEditingPrivate(false); setPrivateInput(privateNote?.content ?? ""); }}
                      className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs hover:border-gray-500 transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={savingPrivate}
                      className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
                    >
                      {savingPrivate ? "Saving…" : "Save"}
                    </button>
                  </div>
                </form>
              ) : privateNote?.content ? (
                <p className="text-sm text-gray-300 whitespace-pre-wrap">{privateNote.content}</p>
              ) : (
                <p className="text-sm text-gray-600">No private notes yet.</p>
              )}
            </section>
          );
        })()}

        {/* Public note panel — GM only */}
        {isGm && (() => {
          const publicNote = myNotes.find((n) => n.visibility === "public");
          return (
            <section className="rounded-xl border border-amber-900/40 bg-gray-900 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-400">GM Notes
                  <span className="ml-2 text-xs rounded-full bg-amber-900/50 text-amber-300 px-2 py-0.5">Public — shared with players</span>
                </h3>
                {!editingPublic && (
                  <button
                    onClick={() => setEditingPublic(true)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                  >
                    {publicNote ? "Edit" : "Add note"}
                  </button>
                )}
              </div>
              {editingPublic ? (
                <form
                  onSubmit={(e) => { e.preventDefault(); handleSaveNote("public", publicInput, setSavingPublic, setEditingPublic); }}
                  className="space-y-2"
                >
                  <textarea
                    rows={4}
                    autoFocus
                    value={publicInput}
                    onChange={(e) => setPublicInput(e.target.value)}
                    placeholder="Notes to share with all players in the campaign journal…"
                    className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => { setEditingPublic(false); setPublicInput(publicNote?.content ?? ""); }}
                      className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs hover:border-gray-500 transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={savingPublic}
                      className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium hover:bg-amber-500 disabled:opacity-50 transition"
                    >
                      {savingPublic ? "Saving…" : "Save"}
                    </button>
                  </div>
                </form>
              ) : publicNote?.content ? (
                <p className="text-sm text-gray-300 whitespace-pre-wrap">{publicNote.content}</p>
              ) : (
                <p className="text-sm text-gray-600">No public notes yet.</p>
              )}
            </section>
          );
        })()}

        {/* Attendance — completed sessions, GM view */}
        {session.status === "completed" && isGm && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <h3 className="text-sm font-medium text-gray-400 mb-4">Attendance</h3>
            {attendance.length === 0 ? (
              <p className="text-sm text-gray-600">No members found.</p>
            ) : (
              <ul className="space-y-2">
                {attendance.map((a) => (
                  <li key={a.user_id} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{a.display_name}</span>
                    <button
                      onClick={() => handleToggleAttendance(a.user_id, a.attended)}
                      disabled={attendanceBusy === a.user_id}
                      className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition ${
                        a.attended
                          ? "bg-green-900/50 text-green-300 hover:bg-green-900"
                          : "bg-gray-800 text-gray-500 hover:bg-gray-700 hover:text-gray-300"
                      } disabled:opacity-50`}
                    >
                      {attendanceBusy === a.user_id ? "…" : a.attended ? "✓ Attended" : "Absent"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* Transcript & summary — populated by the Discord bot */}
        {(session.summary || session.transcript) && (
          <RecordingSection session={session} />
        )}
      </main>
    </div>
  );
}
