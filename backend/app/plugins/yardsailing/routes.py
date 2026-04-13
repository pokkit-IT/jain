from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .services import (
    CreateSaleInput,
    create_sale,
    delete_sale,
    get_sale_by_id,
    list_recent_sales,
    list_sales_for_owner,
    update_sale,
)
from .tags import CURATED_TAGS


router = APIRouter(prefix="/api/plugins/yardsailing", tags=["yardsailing"])


class CreateSaleBody(BaseModel):
    title: str
    address: str
    description: str | None = None
    start_date: str
    end_date: str | None = None
    start_time: str
    end_time: str
    tags: list[str] = Field(default_factory=list)


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

    @classmethod
    def from_model(cls, sale) -> "SaleResponse":
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
