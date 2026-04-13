from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


def _sale_id() -> str:
    return str(uuid4())


class Sale(Base):
    """A yard sale listing owned by a JAIN user.

    Table is prefixed with `yardsailing_` per the internal-plugin naming
    convention so plugin tables can't collide with JAIN core tables.
    """

    __tablename__ = "yardsailing_sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_sale_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    owner: Mapped[User] = relationship()
    tag_rows: Mapped[list["SaleTag"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    day_rows: Mapped[list["SaleDay"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SaleDay.day_date",
    )

    @property
    def tags(self) -> list[str]:
        return sorted({t.tag for t in self.tag_rows})

    def hours_for_day(self, day_iso: str) -> tuple[str, str]:
        """Return (start_time, end_time) for a given ISO date.

        Honors a SaleDay override when one exists; otherwise falls back to
        the sale's default start_time/end_time.
        """
        for row in self.day_rows:
            if row.day_date == day_iso:
                return row.start_time, row.end_time
        return self.start_time, self.end_time


class SaleTag(Base):
    """A tag applied to a Sale (e.g. "furniture", "toys", "baby items").

    Stored lowercased for case-insensitive matching. (sale_id, tag) is the PK
    so duplicate tags on a sale are impossible.
    """

    __tablename__ = "yardsailing_sale_tags"

    sale_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("yardsailing_sales.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)

    sale: Mapped[Sale] = relationship(back_populates="tag_rows")


class SaleDay(Base):
    """Per-day start/end time override for multi-day sales.

    If a sale spans multiple days and the hours differ, a row goes here
    for each day with non-default hours. When no row exists for a given
    day in the range, the Sale's default start_time/end_time applies.
    """

    __tablename__ = "yardsailing_sale_days"

    sale_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("yardsailing_sales.id", ondelete="CASCADE"),
        primary_key=True,
    )
    day_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="day_rows")
