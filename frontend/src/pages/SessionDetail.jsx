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
  fetchSession,
  fetchVotes,
  updateSession,
} from "../api/sessions.js";
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

  // Edit-notes form
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);

  const isGm = members.some((m) => m.user_id === user?.id && m.role === "gm");

  useEffect(() => {
    fetchSession(id)
      .then((s) => {
        setSession(s);
        setNotes(s.session_notes ?? "");
        return Promise.all([fetchMembers(s.campaign_id), fetchVotes(s.id)]);
      })
      .then(([m, v]) => {
        setMembers(m);
        setVotes(v);
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

          {/* GM actions */}
          {isGm && (
            <div className="mt-4 flex gap-2 flex-wrap">
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
      </main>
    </div>
  );
}
