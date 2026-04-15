"""Sale group service: create, search, attach/detach, date-window validation.

Groups collect individual sales under a named event (e.g. "100 Mile Yard
Sale"). When a group has start_date/end_date, member sales must fall fully
within that window.
"""

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .models import Sale, SaleGroup


class GroupError(Exception):
    """Base for group validation errors."""


class GroupNameTaken(GroupError):
    pass


class GroupDateMismatch(GroupError):
    """Raised when a sale's dates fall outside a group's date window."""

    def __init__(self, group: SaleGroup, message: str):
        super().__init__(message)
        self.group = group


@dataclass
class CreateGroupInput:
    name: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "group"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug = base
    n = 2
    while True:
        exists = await db.scalar(
            select(SaleGroup.id).where(SaleGroup.slug == slug).limit(1)
        )
        if not exists:
            return slug
        slug = f"{base}-{n}"
        n += 1


def validate_dates_within_group(sale: Sale, group: SaleGroup) -> bool:
    """True if `sale` fits inside `group`'s date window. Open groups always pass."""
    if not group.start_date or not group.end_date:
        return True
    sale_end = sale.end_date or sale.start_date
    return group.start_date <= sale.start_date and sale_end <= group.end_date


async def search_groups(
    db: AsyncSession, query: str = "", limit: int = 20,
) -> list[SaleGroup]:
    """Case-insensitive prefix match on name. Empty query returns all, sorted by name."""
    stmt = select(SaleGroup).order_by(SaleGroup.name).limit(limit)
    q = (query or "").strip()
    if q:
        stmt = stmt.where(func.lower(SaleGroup.name).like(f"{q.lower()}%"))
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_group(db: AsyncSession, group_id: str) -> SaleGroup | None:
    return await db.get(SaleGroup, group_id)


async def create_group(
    db: AsyncSession, user: User, data: CreateGroupInput,
) -> SaleGroup:
    name = (data.name or "").strip()
    if len(name) < 1 or len(name) > 120:
        raise GroupError("name must be 1-120 characters")

    # Case-insensitive uniqueness
    exists = await db.scalar(
        select(SaleGroup.id).where(func.lower(SaleGroup.name) == name.lower()).limit(1)
    )
    if exists:
        raise GroupNameTaken(f"A group named '{name}' already exists")

    if (data.start_date is None) != (data.end_date is None):
        raise GroupError("start_date and end_date must both be set or both be null")
    if data.start_date and data.end_date and data.start_date > data.end_date:
        raise GroupError("start_date must be on or before end_date")

    slug = await _unique_slug(db, _slugify(name))
    group = SaleGroup(
        name=name,
        slug=slug,
        description=(data.description or None),
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=user.id,
    )
    db.add(group)
    await db.flush()
    return group


async def attach_sale_to_group(
    db: AsyncSession, sale: Sale, group: SaleGroup,
) -> None:
    if not validate_dates_within_group(sale, group):
        raise GroupDateMismatch(
            group,
            f"Sale dates ({sale.start_date}..{sale.end_date or sale.start_date}) "
            f"are outside group '{group.name}' window "
            f"({group.start_date}..{group.end_date})",
        )
    if group in sale.groups:
        return
    sale.groups.append(group)
    await db.flush()


async def detach_sale_from_group(
    db: AsyncSession, sale: Sale, group: SaleGroup,
) -> None:
    if group not in sale.groups:
        return
    sale.groups.remove(group)
    await db.flush()


async def set_sale_groups(
    db: AsyncSession, sale: Sale, group_ids: list[str],
) -> list[SaleGroup]:
    """Replace the sale's group memberships with the given ids. Validates all.

    Raises GroupDateMismatch on the first group that doesn't accept the
    sale's dates, without mutating the sale.
    """
    target_ids = list(dict.fromkeys(group_ids))  # dedupe, preserve order
    if not target_ids:
        sale.groups.clear()
        await db.flush()
        return []

    res = await db.execute(select(SaleGroup).where(SaleGroup.id.in_(target_ids)))
    groups = list(res.scalars().all())
    found_ids = {g.id for g in groups}
    missing = [gid for gid in target_ids if gid not in found_ids]
    if missing:
        raise GroupError(f"Unknown group id(s): {missing}")

    for g in groups:
        if not validate_dates_within_group(sale, g):
            raise GroupDateMismatch(
                g,
                f"Sale dates don't fit group '{g.name}' "
                f"({g.start_date}..{g.end_date})",
            )

    sale.groups.clear()
    for g in groups:
        sale.groups.append(g)
    await db.flush()
    return groups
