/**
 * CampaignNotes — aggregated session journal for a campaign.
 *
 * Shows every session (in chronological order) for which the current user
 * has written a note, plus any public GM notes.  GMs see their own notes
 * (private or public) alongside a label indicating visibility.
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchCampaignNotes } from "../api/campaigns.js";
import { fetchCampaign } from "../api/campaigns.js";

function fmtDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });
}

export default function CampaignNotes() {
  const { id: campaignId } = useParams();

  const [campaign, setCampaign] = useState(null);
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetchCampaign(campaignId),
      fetchCampaignNotes(campaignId),
    ])
      .then(([c, n]) => {
        setCampaign(c);
        setNotes(n);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <p className="text-gray-500">Loading journal…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-gray-950 gap-4">
        <p className="text-red-400">{error}</p>
        <Link to="/dashboard" className="text-sm text-indigo-400 hover:underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link
          to={`/campaigns/${campaignId}`}
          className="text-gray-500 hover:text-white transition text-sm"
        >
          ← {campaign?.name ?? "Campaign"}
        </Link>
        <span className="text-gray-700">/</span>
        <span className="font-semibold">Campaign Journal</span>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8">
        <p className="text-sm text-gray-500 mb-6">
          Your session notes, plus any GM notes shared with the group.
        </p>

        {notes.length === 0 ? (
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-8 text-center">
            <p className="text-gray-500 text-sm">No notes written yet.</p>
            <p className="text-gray-600 text-xs mt-2">
              Write notes on individual sessions to build your journal.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {notes.map((entry) => (
              <article
                key={entry.session_id}
                className="rounded-xl border border-gray-800 bg-gray-900 p-5"
              >
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <Link
                      to={`/sessions/${entry.session_id}`}
                      className="font-semibold hover:text-indigo-400 transition"
                    >
                      {entry.session_title ?? "Untitled Session"}
                    </Link>
                    {entry.confirmed_time && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {fmtDate(entry.confirmed_time)}
                      </p>
                    )}
                  </div>
                </div>

                {entry.my_notes?.length > 0 && (
                  <div className="mb-3 space-y-3">
                    <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
                      My Notes
                    </p>
                    {entry.my_notes.map((note, i) => (
                      <p key={i} className="text-sm text-gray-300 whitespace-pre-wrap">{note}</p>
                    ))}
                  </div>
                )}

                {entry.gm_public_note && (
                  <div className={entry.my_notes?.length > 0 ? "mt-4 pt-4 border-t border-gray-800" : ""}>
                    <p className="text-xs text-amber-500 font-medium uppercase tracking-wide mb-1">
                      GM Notes
                    </p>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap">
                      {entry.gm_public_note}
                    </p>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
