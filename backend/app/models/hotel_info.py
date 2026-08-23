"""
HotelInfo model.

Simple key-fact store the AI will query when a customer asks things like
"what time is check-in?" or "do you have free wifi?" (Phase 17).
`topic` is a short slug we match against; `answer` is what the AI reads out.
This keeps the AI from hallucinating hotel policy - it must look this up.
"""

from sqlalchemy import Column, Integer, String, Text

from app.database.db import Base


class HotelInfo(Base):
    __tablename__ = "hotel_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(50), nullable=False)   # e.g. "checkin_time", "wifi"
    answer = Column(Text, nullable=False)

    def __repr__(self):
        return f"<HotelInfo {self.topic}>"
