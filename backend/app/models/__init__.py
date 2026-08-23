"""
Importing every model here means a single `import app.models` (or
`from app.models import *`) registers all tables with SQLAlchemy's
Base.metadata - which is what create_all() needs to build them.
"""

from app.models.room import Room
from app.models.customer import Customer
from app.models.booking import Booking
from app.models.hotel_info import HotelInfo

__all__ = ["Room", "Customer", "Booking", "HotelInfo"]
