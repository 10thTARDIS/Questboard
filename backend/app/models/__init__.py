# Import all models here so that:
#   1. Alembic env.py picks up every table via `import app.models`
#   2. SQLAlchemy registers all relationships before any mapper is used
#
# Add new model modules below as they are created.

from app.models.user import User as User  # noqa: F401
from app.models.campaign import Campaign as Campaign, CampaignMember as CampaignMember  # noqa: F401
from app.models.session import Session as Session  # noqa: F401
from app.models.timeslot import TimeSlot as TimeSlot  # noqa: F401
from app.models.vote import Vote as Vote  # noqa: F401
