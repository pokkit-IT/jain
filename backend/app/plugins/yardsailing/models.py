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

    @property
    def tags(self) -> list[str]:
        return sorted({t.tag for t in self.tag_rows})


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
