"""
Customer model.

Phone number is unique because we'll use it to look up existing
bookings later (Phase 14 - cancellation flow: "give me your phone number").
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)
    email = Column(String(100), nullable=True)

    bookings = relationship("Booking", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.name} ({self.phone})>"
