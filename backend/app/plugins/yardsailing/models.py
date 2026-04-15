from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


def _sale_id() -> str:
    return str(uuid4())


sale_group_memberships = Table(
    "yardsailing_sale_group_memberships",
    Base.metadata,
    Column(
        "sale_id",
        String(36),
        ForeignKey("yardsailing_sales.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        String(36),
        ForeignKey("yardsailing_sale_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


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
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="host", server_default="host",
    )
    confirmations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
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
    photos: Mapped[list["SalePhoto"]] = relationship(
        "SalePhoto",
        cascade="all, delete-orphan",
        order_by="SalePhoto.position",
        lazy="selectin",
    )
    groups: Mapped[list["SaleGroup"]] = relationship(
        "SaleGroup",
        secondary=sale_group_memberships,
        back_populates="sales",
        lazy="selectin",
        order_by="SaleGroup.name",
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


class SalePhoto(Base):
    """A photo attached to a Sale.

    Ordered by `position` for deterministic display order. Cascade-deleted
    when the parent Sale is removed.
    """

    __tablename__ = "yardsailing_sale_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sale_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("yardsailing_sales.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class SaleGroup(Base):
    """A named grouping of sales (e.g. "100 Mile Yard Sale").

    Optional date window constrains membership: if `start_date`/`end_date` are
    set, a sale can only join when its own dates fall fully within the window.
    Name uniqueness is case-insensitive (enforced in the service layer).
    """

    __tablename__ = "yardsailing_sale_groups"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_yardsailing_sale_groups_slug"),
        CheckConstraint(
            "(start_date IS NULL AND end_date IS NULL) OR "
            "(start_date IS NOT NULL AND end_date IS NOT NULL AND start_date <= end_date)",
            name="ck_yardsailing_sale_groups_dates",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_sale_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    creator: Mapped[User] = relationship()
    sales: Mapped[list[Sale]] = relationship(
        Sale,
        secondary=sale_group_memberships,
        back_populates="groups",
        lazy="selectin",
    )
