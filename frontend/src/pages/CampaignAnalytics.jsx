/**
 * CampaignAnalytics — session frequency, attendance, and vote participation
 * stats for a campaign.  Accessible to all campaign members.
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchCampaign, fetchCampaignAnalytics } from "../api/campaigns.js";

function pct(rate) {
  if (rate === null || rate === undefined) return "—";
  return `${Math.round(rate * 100)}%`;
}

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 px-5 py-4">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm text-gray-400 mt-0.5">{label}</p>
      {sub && <p className="text-xs text-gray-600 mt-1">{sub}</p>}
    </div>
  );
}

export default function CampaignAnalytics() {
  const { id: campaignId } = useParams();

  const [campaign, setCampaign] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([fetchCampaign(campaignId), fetchCampaignAnalytics(campaignId)])
      .then(([c, a]) => {
        setCampaign(c);
        setAnalytics(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <p className="text-gray-500">Loading analytics…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  const a = analytics;

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
        <span className="font-semibold">Analytics</span>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 space-y-8">

        {/* Session overview */}
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">Sessions</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Total" value={a.total_sessions} />
            <StatCard label="Completed" value={a.completed_sessions} />
            <StatCard label="Upcoming" value={a.confirmed_sessions} />
            <StatCard label="Cancelled" value={a.cancelled_sessions} />
          </div>
        </section>

        {/* Frequency */}
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">Frequency</h2>
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              label="Avg. gap between sessions"
              value={a.average_gap_days !== null ? `${a.average_gap_days}d` : "—"}
              sub={a.completed_sessions < 2 ? "Need at least 2 completed sessions" : null}
            />
            <StatCard
              label="Completed in last 30 days"
              value={a.sessions_last_30_days}
            />
          </div>
        </section>

        {/* Member stats */}
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">Members</h2>
          {a.members.length === 0 ? (
            <p className="text-sm text-gray-500">No members found.</p>
          ) : (
            <div className="rounded-xl border border-gray-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                    <th className="px-4 py-3 text-left font-medium">Member</th>
                    <th className="px-4 py-3 text-center font-medium">Attendance</th>
                    <th className="px-4 py-3 text-center font-medium">Vote participation</th>
                  </tr>
                </thead>
                <tbody>
                  {a.members.map((m, i) => (
                    <tr
                      key={m.user_id}
                      className={i < a.members.length - 1 ? "border-b border-gray-800" : ""}
                    >
                      <td className="px-4 py-3">
                        <span className="font-medium">{m.display_name}</span>
                        {m.role === "gm" && (
                          <span className="ml-2 text-xs text-indigo-400">GM</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={getRateClass(m.attendance_rate)}>
                          {pct(m.attendance_rate)}
                        </span>
                        <span className="block text-xs text-gray-600">
                          {m.sessions_attended}/{m.sessions_eligible}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={getRateClass(m.vote_participation_rate)}>
                          {pct(m.vote_participation_rate)}
                        </span>
                        <span className="block text-xs text-gray-600">
                          {m.vote_sessions_participated}/{m.vote_sessions_eligible}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-xs text-gray-600">
            Attendance and vote participation only count sessions created after each member joined.
          </p>
        </section>

      </main>
    </div>
  );
}

function getRateClass(rate) {
  if (rate === null || rate === undefined) return "text-gray-500";
  if (rate >= 0.8) return "text-green-400";
  if (rate >= 0.5) return "text-yellow-400";
  return "text-red-400";
}
