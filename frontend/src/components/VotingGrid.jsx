/**
 * VotingGrid — interactive availability grid for vote-mode sessions.
 *
 * Props:
 *   session     {object}   Session object with `time_slots` array
 *   members     {object[]} Campaign members (user_id, display_name, role, …)
 *   currentUser {object}   The authenticated user (id, display_name, …)
 *   initialVotes {object[]} Pre-fetched votes from GET /sessions/{id}/votes
 *
 * Behaviour:
 *   - Each row is a time slot; each column is a member who has voted.
 *   - The current user's cells are interactive buttons that cycle through
 *     yes → maybe → no → (cleared) on each click.
 *   - The slot with the highest score is highlighted with ★ and a green tint.
 *   - Scoring: yes = +2, maybe = +1, no = 0.
 */

import { useState } from "react";
import { deleteVote, submitVote } from "../api/sessions.js";

const AVAIL_STYLES = {
  yes:   "bg-green-700/60 text-green-300",
  maybe: "bg-yellow-700/40 text-yellow-300",
  no:    "bg-red-900/40 text-red-400",
};

const AVAIL_LABEL = { yes: "✓", maybe: "~", no: "✗" };

// Clicking cycles through this sequence; null means "delete the vote".
const NEXT_AVAIL = { undefined: "yes", yes: "maybe", maybe: "no", no: null };

/** Sum the availability votes for one slot: yes=2, maybe=1, no=0. */
function slotScore(voteMap) {
  return Object.values(voteMap ?? {}).reduce((s, a) => {
    return s + (a === "yes" ? 2 : a === "maybe" ? 1 : 0);
  }, 0);
}

/** Format an ISO datetime string for display in the grid header. */
function fmt(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function VotingGrid({ session, members, currentUser, initialVotes }) {
  const [votes, setVotes] = useState(initialVotes);
  const [busy, setBusy] = useState(null); // slotId currently being updated

  // Build lookup: slotId → userId → availability
  const bySlot = {};
  for (const v of votes) {
    const sid = String(v.time_slot_id);
    const uid = String(v.user_id);
    if (!bySlot[sid]) bySlot[sid] = {};
    bySlot[sid][uid] = v.availability;
  }

  // Score per slot and overall best score
  const scores = {};
  for (const slot of session.time_slots) {
    scores[String(slot.id)] = slotScore(bySlot[String(slot.id)]);
  }
  const maxScore = Math.max(0, ...Object.values(scores));

  // Show all members who have voted, plus current user (always shown)
  const votedUserIds = new Set(votes.map((v) => String(v.user_id)));
  votedUserIds.add(String(currentUser.id));
  const displayMembers = members.filter((m) => votedUserIds.has(String(m.user_id)));

  const handleClick = async (slotId) => {
    if (busy) return;
    const myAvail = bySlot[String(slotId)]?.[String(currentUser.id)];
    const next = NEXT_AVAIL[myAvail];

    setBusy(slotId);
    try {
      if (next === null) {
        await deleteVote(session.id, slotId);
        setVotes((prev) =>
          prev.filter(
            (v) =>
              !(String(v.time_slot_id) === String(slotId) &&
                String(v.user_id) === String(currentUser.id))
          )
        );
      } else {
        const vote = await submitVote(session.id, slotId, next);
        setVotes((prev) => [
          ...prev.filter(
            (v) =>
              !(String(v.time_slot_id) === String(slotId) &&
                String(v.user_id) === String(currentUser.id))
          ),
          vote,
        ]);
      }
    } catch (e) {
      console.error("Vote error:", e);
    } finally {
      setBusy(null);
    }
  };

  if (session.time_slots.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium">
              Time
            </th>
            {displayMembers.map((m) => (
              <th
                key={m.user_id}
                className="px-2 py-2 text-xs text-gray-500 font-medium text-center"
              >
                <span className="block max-w-[56px] truncate" title={m.display_name}>
                  {m.display_name.split(" ")[0]}
                  {String(m.user_id) === String(currentUser.id) && (
                    <span className="text-indigo-500">*</span>
                  )}
                </span>
              </th>
            ))}
            <th className="px-3 py-2 text-xs text-gray-500 font-medium text-right">
              Score
            </th>
          </tr>
        </thead>
        <tbody>
          {session.time_slots.map((slot) => {
            const slotId = String(slot.id);
            const isWinner = maxScore > 0 && scores[slotId] === maxScore;
            const myAvail = bySlot[slotId]?.[String(currentUser.id)];

            return (
              <tr
                key={slot.id}
                className={`border-t border-gray-800 ${
                  isWinner ? "bg-green-900/10" : ""
                }`}
              >
                <td className="px-3 py-2.5 text-xs text-gray-300 whitespace-nowrap">
                  {fmt(slot.proposed_time)}
                  {isWinner && (
                    <span className="ml-1.5 text-green-500">★</span>
                  )}
                </td>

                {displayMembers.map((m) => {
                  const avail = bySlot[slotId]?.[String(m.user_id)];
                  const isMe = String(m.user_id) === String(currentUser.id);

                  return (
                    <td key={m.user_id} className="px-2 py-1.5 text-center">
                      {isMe ? (
                        <button
                          onClick={() => handleClick(slot.id)}
                          disabled={!!busy}
                          title={
                            avail
                              ? `Your vote: ${avail} — click to change`
                              : "Click to vote"
                          }
                          className={`w-8 h-7 rounded text-xs font-medium transition ${
                            avail
                              ? AVAIL_STYLES[avail]
                              : "border border-dashed border-gray-700 text-gray-600 hover:border-indigo-600 hover:text-indigo-400"
                          } ${
                            busy === slot.id
                              ? "opacity-50 cursor-wait"
                              : "cursor-pointer"
                          }`}
                        >
                          {avail ? AVAIL_LABEL[avail] : "?"}
                        </button>
                      ) : (
                        <span
                          className={`inline-flex items-center justify-center w-8 h-7 rounded text-xs font-medium ${
                            avail ? AVAIL_STYLES[avail] : "text-gray-700"
                          }`}
                        >
                          {avail ? AVAIL_LABEL[avail] : "—"}
                        </span>
                      )}
                    </td>
                  );
                })}

                <td className="px-3 py-2.5 text-right">
                  <span
                    className={`text-xs font-semibold ${
                      isWinner ? "text-green-400" : "text-gray-500"
                    }`}
                  >
                    {scores[slotId]}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <p className="mt-3 text-xs text-gray-600">
        ✓ = Yes (+2) &nbsp;·&nbsp; ~ = Maybe (+1) &nbsp;·&nbsp; ✗ = No
        &nbsp;·&nbsp; * = you &nbsp;·&nbsp; ★ = best slot
      </p>
    </div>
  );
}
