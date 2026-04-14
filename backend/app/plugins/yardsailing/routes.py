from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .services import (
    CreateSaleInput,
    DayHours,
    create_sale,
    delete_sale,
    expanded_days,
    get_sale_by_id,
    list_recent_sales,
    list_sales_for_owner,
    update_sale,
)
from .models import Sale, SalePhoto
from .photos import delete_photo as _delete_photo, save_photo
from .tags import CURATED_TAGS


router = APIRouter(prefix="/api/plugins/yardsailing", tags=["yardsailing"])


class DayHoursBody(BaseModel):
    day_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM


class CreateSaleBody(BaseModel):
    title: str
    address: str
    description: str | None = None
    start_date: str
    end_date: str | None = None
    start_time: str
    end_time: str
    tags: list[str] = Field(default_factory=list)
    days: list[DayHoursBody] = Field(default_factory=list)


class SalePhotoOut(BaseModel):
    id: str
    position: int
    content_type: str
    url: str
    thumb_url: str


class SaleResponse(BaseModel):
    id: str
    title: str
    address: str
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str
    end_time: str
    lat: float | None
    lng: float | None
    tags: list[str] = Field(default_factory=list)
    # Expanded per-day schedule (one entry per date in the range).
    # Always present; uses SaleDay overrides when set, defaults otherwise.
    days: list[DayHoursBody] = Field(default_factory=list)
    photos: list[SalePhotoOut] = Field(default_factory=list)

    @classmethod
    def from_model(cls, sale) -> "SaleResponse":
        photos_sorted = sorted(sale.photos or [], key=lambda p: p.position)
        return cls(
            id=sale.id,
            title=sale.title,
            address=sale.address,
            description=sale.description,
            start_date=sale.start_date,
            end_date=sale.end_date,
            start_time=sale.start_time,
            end_time=sale.end_time,
            lat=sale.lat,
            lng=sale.lng,
            tags=sale.tags,
            days=[DayHoursBody(**d) for d in expanded_days(sale)],
            photos=[
                SalePhotoOut(
                    id=p.id,
                    position=p.position,
                    content_type=p.content_type,
                    url=f"/uploads/{p.original_path}",
                    thumb_url=f"/uploads/{p.thumb_path}",
                )
                for p in photos_sorted
            ],
        )


class TagListResponse(BaseModel):
    tags: list[str]


@router.get("/tags", response_model=TagListResponse)
async def list_curated_tags_route() -> TagListResponse:
    """Curated tag vocabulary for the SaleForm's chip picker."""
    return TagListResponse(tags=CURATED_TAGS)


@router.post("/sales", status_code=status.HTTP_201_CREATED, response_model=SaleResponse)
async def create_sale_route(
    body: CreateSaleBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    sale = await create_sale(
        db, user,
        CreateSaleInput(
            title=body.title,
            address=body.address,
            description=body.description,
            start_date=body.start_date,
            end_date=body.end_date,
            start_time=body.start_time,
            end_time=body.end_time,
            tags=body.tags,
            days=[
                DayHours(day_date=d.day_date, start_time=d.start_time, end_time=d.end_time)
                for d in body.days
            ],
        ),
    )
    return SaleResponse.from_model(sale)


@router.get("/sales", response_model=list[SaleResponse])
async def list_my_sales_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SaleResponse]:
    sales = await list_sales_for_owner(db, user)
    return [SaleResponse.from_model(s) for s in sales]


@router.get("/sales/recent", response_model=list[SaleResponse])
async def list_recent_sales_route(
    db: AsyncSession = Depends(get_db),
    tag: list[str] = Query(default_factory=list),
    q: str | None = Query(default=None),
    happening_now: bool = Query(default=False),
) -> list[SaleResponse]:
    """Public: recent sales across users, for the map.

    Query params:
      - tag: one or more tag names (repeat: ?tag=toys&tag=tools)
      - q: free-text search across title, description, and tags
      - happening_now: only sales in progress right now
    """
    sales = await list_recent_sales(
        db,
        limit=100,
        tags=tag or None,
        query=q,
        only_happening_now=happening_now,
    )
    return [SaleResponse.from_model(s) for s in sales]


@router.get("/sales/{sale_id}", response_model=SaleResponse)
async def get_sale_route(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale not found")
    return SaleResponse.from_model(sale)


@router.put("/sales/{sale_id}", response_model=SaleResponse)
async def update_sale_route(
    sale_id: str,
    body: CreateSaleBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale not found")
    if sale.owner_id != user.id:
        raise HTTPException(status_code=403, detail="not your sale")
    updated = await update_sale(
        db, sale,
        CreateSaleInput(
            title=body.title,
            address=body.address,
            description=body.description,
            start_date=body.start_date,
            end_date=body.end_date,
            start_time=body.start_time,
            end_time=body.end_time,
            tags=body.tags,
            days=[
                DayHours(day_date=d.day_date, start_time=d.start_time, end_time=d.end_time)
                for d in body.days
            ],
        ),
    )
    return SaleResponse.from_model(updated)


@router.delete("/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale_route(
    sale_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale not found")
    if sale.owner_id != user.id:
        raise HTTPException(status_code=403, detail="not your sale")
    await delete_sale(db, sale)


def _photo_to_json(photo: SalePhoto) -> dict:
    return {
        "id": photo.id,
        "position": photo.position,
        "content_type": photo.content_type,
        "url": f"/uploads/{photo.original_path}",
        "thumb_url": f"/uploads/{photo.thumb_path}",
    }


@router.post("/sales/{sale_id}/photos")
async def upload_sale_photo(
    sale_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale_not_found")
    if sale.owner_id != user.id:
        raise HTTPException(status_code=403, detail="not_sale_owner")

    photo = await save_photo(db, sale_id, file)
    return _photo_to_json(photo)


@router.delete("/sales/{sale_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale_photo(
    sale_id: str,
    photo_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.owner_id != user.id:
        raise HTTPException(status_code=404, detail="sale_not_found")
    photo = await db.get(SalePhoto, photo_id)
    if photo is None or photo.sale_id != sale_id:
        raise HTTPException(status_code=404, detail="photo_not_found")
    await _delete_photo(db, photo)
    return None


class ReorderRequest(BaseModel):
    photo_ids: list[str]


@router.patch("/sales/{sale_id}/photos/reorder")
async def reorder_sale_photos(
    sale_id: str,
    body: ReorderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.owner_id != user.id:
        raise HTTPException(status_code=404, detail="sale_not_found")

    res = await db.execute(select(SalePhoto).where(SalePhoto.sale_id == sale_id))
    existing = {p.id: p for p in res.scalars().all()}
    if set(existing.keys()) != set(body.photo_ids):
        raise HTTPException(status_code=400, detail="photo_ids_mismatch")

    for index, pid in enumerate(body.photo_ids):
        existing[pid].position = index
    await db.commit()

    return [_photo_to_json(existing[pid]) for pid in body.photo_ids]
