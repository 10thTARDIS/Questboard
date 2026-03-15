"""Campaign analytics — aggregation over existing session, attendance, and vote data.

No new tables are required.  All computations are done against the data
already stored by the scheduling and attendance features.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import CampaignMember
from app.models.session import SchedulingMode, Session, SessionStatus
from app.models.session_attendance import SessionAttendance
from app.models.timeslot import TimeSlot
from app.models.user import User
from app.models.vote import Vote


@dataclass
class MemberStats:
    user_id: uuid.UUID
    display_name: str
    role: str
    sessions_eligible: int
    sessions_attended: int
    attendance_rate: float | None
    vote_sessions_eligible: int
    vote_sessions_participated: int
    vote_participation_rate: float | None


@dataclass
class CampaignAnalytics:
    total_sessions: int
    proposed_sessions: int
    confirmed_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    average_gap_days: float | None
    sessions_last_30_days: int
    members: list[MemberStats]


async def get_campaign_analytics(
    db: AsyncSession, campaign_id: uuid.UUID
) -> CampaignAnalytics:
    """Compute analytics for a campaign.

    Makes four queries (sessions, members+users, attendance, votes) and
    processes everything in Python to avoid complex SQL.
    """

    # ── Sessions ───────────────────────────────────────────────────────────────

    sessions_result = await db.execute(
        select(Session).where(Session.campaign_id == campaign_id)
    )
    sessions: list[Session] = list(sessions_result.scalars().all())

    by_status: dict[str, int] = {s.value: 0 for s in SessionStatus}
    for s in sessions:
        by_status[s.status.value] += 1

    # Completed sessions ordered by confirmed_time — used for gap + last-30-days
    completed = sorted(
        [s for s in sessions if s.status == SessionStatus.completed and s.confirmed_time],
        key=lambda s: s.confirmed_time,  # type: ignore[arg-type]
    )

    average_gap_days: float | None = None
    if len(completed) >= 2:
        gaps = [
            (completed[i + 1].confirmed_time - completed[i].confirmed_time).total_seconds() / 86400  # type: ignore[operator]
            for i in range(len(completed) - 1)
        ]
        average_gap_days = round(sum(gaps) / len(gaps), 1)

    now = datetime.now(timezone.utc)
    sessions_last_30 = sum(
        1 for s in completed
        if s.confirmed_time and (now - s.confirmed_time) <= timedelta(days=30)
    )

    # ── Members ────────────────────────────────────────────────────────────────

    members_result = await db.execute(
        select(CampaignMember, User)
        .join(User, User.id == CampaignMember.user_id)
        .where(CampaignMember.campaign_id == campaign_id)
    )
    member_rows: list[tuple[CampaignMember, User]] = list(members_result.all())

    # ── Attendance records ─────────────────────────────────────────────────────

    session_ids = [s.id for s in sessions]
    if session_ids:
        att_result = await db.execute(
            select(SessionAttendance).where(
                SessionAttendance.session_id.in_(session_ids)
            )
        )
        attendance_records: list[SessionAttendance] = list(att_result.scalars().all())
    else:
        attendance_records = []

    # user_id → set of session_ids they attended (attended=True)
    attended_by_user: dict[uuid.UUID, set[uuid.UUID]] = {}
    for rec in attendance_records:
        if rec.attended:
            attended_by_user.setdefault(rec.user_id, set()).add(rec.session_id)

    # ── Votes ──────────────────────────────────────────────────────────────────

    vote_sessions = [s for s in sessions if s.scheduling_mode == SchedulingMode.vote]
    vote_session_ids = [s.id for s in vote_sessions]

    # user_id → set of session_ids they voted on (at least one slot)
    voted_on_by_user: dict[uuid.UUID, set[uuid.UUID]] = {}
    if vote_session_ids:
        votes_result = await db.execute(
            select(Vote, TimeSlot)
            .join(TimeSlot, TimeSlot.id == Vote.time_slot_id)
            .where(TimeSlot.session_id.in_(vote_session_ids))
        )
        for vote, slot in votes_result.all():
            voted_on_by_user.setdefault(vote.user_id, set()).add(slot.session_id)

    # ── Per-member stats ───────────────────────────────────────────────────────

    member_stats: list[MemberStats] = []
    for member, user in member_rows:
        joined = member.joined_at

        # A session is "eligible" for a member if it was created after they joined
        eligible_completed = [s for s in completed if s.created_at >= joined]
        n_eligible = len(eligible_completed)
        eligible_ids = {s.id for s in eligible_completed}
        n_attended = len(attended_by_user.get(user.id, set()) & eligible_ids)
        attendance_rate = round(n_attended / n_eligible, 3) if n_eligible else None

        eligible_vote = [s for s in vote_sessions if s.created_at >= joined]
        n_vote_eligible = len(eligible_vote)
        eligible_vote_ids = {s.id for s in eligible_vote}
        n_voted = len(voted_on_by_user.get(user.id, set()) & eligible_vote_ids)
        vote_rate = round(n_voted / n_vote_eligible, 3) if n_vote_eligible else None

        member_stats.append(MemberStats(
            user_id=user.id,
            display_name=user.effective_display_name,
            role=member.role.value,
            sessions_eligible=n_eligible,
            sessions_attended=n_attended,
            attendance_rate=attendance_rate,
            vote_sessions_eligible=n_vote_eligible,
            vote_sessions_participated=n_voted,
            vote_participation_rate=vote_rate,
        ))

    # GMs first, then alphabetical
    member_stats.sort(key=lambda m: (0 if m.role == "gm" else 1, m.display_name.lower()))

    return CampaignAnalytics(
        total_sessions=len(sessions),
        proposed_sessions=by_status.get("proposed", 0),
        confirmed_sessions=by_status.get("confirmed", 0),
        completed_sessions=by_status.get("completed", 0),
        cancelled_sessions=by_status.get("cancelled", 0),
        average_gap_days=average_gap_days,
        sessions_last_30_days=sessions_last_30,
        members=member_stats,
    )
