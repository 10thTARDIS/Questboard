import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.session import SchedulingMode, SessionStatus
from app.models.session_note import NoteVisibility


# ── Timeslot ──────────────────────────────────────────────────────────────────

class TimeSlotResponse(BaseModel):
    id: uuid.UUID
    proposed_time: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TimeSlotCreate(BaseModel):
    proposed_time: datetime


# ── Session input ─────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str | None = None
    description: str | None = None
    scheduling_mode: SchedulingMode
    # vote: 2–5 times  |  direct/tentative: exactly 1 time
    proposed_times: list[datetime]

    @model_validator(mode="after")
    def validate_proposed_times(self) -> "SessionCreate":
        times = self.proposed_times
        if not times:
            raise ValueError("At least one proposed time is required")
        if self.scheduling_mode == SchedulingMode.vote:
            if len(times) < 2 or len(times) > 5:
                raise ValueError("Vote mode requires 2–5 proposed times")
        else:
            if len(times) != 1:
                raise ValueError("Direct/tentative mode requires exactly 1 proposed time")
        return self


class SessionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    session_notes: str | None = None  # GM adds post-session notes
    # For editing proposed times on a non-confirmed session (vote mode)
    proposed_times: list[datetime] | None = None
    # For rescheduling a confirmed session to a new time
    reschedule_time: datetime | None = None


class ConfirmRequest(BaseModel):
    # Required for vote mode (the winning slot); omit for direct/tentative.
    time_slot_id: uuid.UUID | None = None


# ── Session output ────────────────────────────────────────────────────────────

class SessionListItem(BaseModel):
    """Lightweight representation returned in campaign session lists."""
    id: uuid.UUID
    campaign_id: uuid.UUID
    title: str | None
    scheduling_mode: SchedulingMode
    status: SessionStatus
    confirmed_time: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Full session detail including time slots."""
    id: uuid.UUID
    campaign_id: uuid.UUID
    title: str | None
    description: str | None
    scheduling_mode: SchedulingMode
    status: SessionStatus
    confirmed_time: datetime | None
    session_notes: str | None
    created_by: uuid.UUID
    created_at: datetime
    time_slots: list[TimeSlotResponse]
    # v2.0 transcription fields — null until the recording bot populates them
    recording_url: str | None = None
    transcript: str | None = None
    summary: str | None = None
    transcript_updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Session notes ──────────────────────────────────────────────────────────────

class SessionNoteUpsert(BaseModel):
    content: str
    visibility: NoteVisibility = NoteVisibility.private


class SessionNoteResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    visibility: NoteVisibility
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Attendance ──────────────────────────────────────────────────────────────────

class AttendanceEntry(BaseModel):
    user_id: uuid.UUID
    display_name: str
    attended: bool

    model_config = {"from_attributes": True}


class AttendanceUpsert(BaseModel):
    attended: bool


# ── Campaign notes (aggregated journal) ────────────────────────────────────────

class CampaignNoteEntry(BaseModel):
    session_id: uuid.UUID
    session_title: str | None
    confirmed_time: datetime | None
    my_notes: list[str]  # all of the user's own notes (private + public)
    gm_public_note: str | None

    model_config = {"from_attributes": True}
