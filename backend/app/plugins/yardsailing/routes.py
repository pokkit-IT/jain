from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .services import (
    CreateSaleInput,
    create_sale,
    get_sale_by_id,
    list_sales_for_owner,
)


router = APIRouter(prefix="/api/plugins/yardsailing", tags=["yardsailing"])


class CreateSaleBody(BaseModel):
    title: str
    address: str
    description: str | None = None
    start_date: str
    end_date: str | None = None
    start_time: str
    end_time: str


class SaleResponse(BaseModel):
    id: str
    title: str
    address: str
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str
    end_time: str

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
        )


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


@router.get("/sales/{sale_id}", response_model=SaleResponse)
async def get_sale_route(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale not found")
    return SaleResponse.from_model(sale)
