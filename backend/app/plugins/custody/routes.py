from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .export import export_csv, export_pdf
from .models import Child, CustodyEvent, EventPhoto, Schedule, ScheduleException
from .photos import delete_event_photo, save_event_photo
from .schedules import compute_status, compute_summary, refresh_missed
from .services import (
    CreateEventInput,
    CreateScheduleInput,
    InvalidEventData,
    InvalidScheduleData,
    add_schedule_exception,
    create_child,
    create_event,
    create_schedule,
    delete_child,
    delete_event,
    delete_schedule,
    delete_schedule_exception,
    get_child,
    get_event,
    get_schedule,
    list_children,
    list_events,
    list_schedules,
    update_child,
    update_event,
    update_schedule,
)

router = APIRouter(prefix="/api/plugins/custody", tags=["custody"])


# ----- Pydantic schemas -----


class ChildBody(BaseModel):
    name: str
    dob: str | None = None


class ChildResponse(BaseModel):
    id: str
    name: str
    dob: str | None

    @classmethod
    def from_model(cls, c: Child) -> "ChildResponse":
        return cls(id=c.id, name=c.name, dob=c.dob)


class EventPhotoOut(BaseModel):
    id: str
    position: int
    content_type: str
    url: str
    thumb_url: str

    @classmethod
    def from_model(cls, p: EventPhoto) -> "EventPhotoOut":
        return cls(
            id=p.id, position=p.position, content_type=p.content_type,
            url=f"/uploads/{p.original_path}",
            thumb_url=f"/uploads/{p.thumb_path}",
        )


class EventBody(BaseModel):
    child_id: str
    type: str
    occurred_at: datetime | None = None
    notes: str | None = None
    location: str | None = None
    overnight: bool = False
    amount_cents: int | None = None
    category: str | None = None
    call_connected: bool | None = None
    missed_source: str | None = None


class EventPatch(BaseModel):
    occurred_at: datetime | None = None
    notes: str | None = None
    location: str | None = None
    overnight: bool | None = None
    amount_cents: int | None = None
    category: str | None = None
    call_connected: bool | None = None


class EventResponse(BaseModel):
    id: str
    child_id: str
    type: str
    occurred_at: datetime
    notes: str | None
    location: str | None
    overnight: bool
    amount_cents: int | None
    category: str | None
    call_connected: bool | None
    missed_source: str | None
    schedule_id: str | None
    photos: list[EventPhotoOut] = Field(default_factory=list)

    @classmethod
    def from_model(cls, e: CustodyEvent) -> "EventResponse":
        return cls(
            id=e.id, child_id=e.child_id, type=e.type,
            occurred_at=e.occurred_at,
            notes=e.notes, location=e.location,
            overnight=bool(e.overnight),
            amount_cents=e.amount_cents, category=e.category,
            call_connected=e.call_connected,
            missed_source=e.missed_source, schedule_id=e.schedule_id,
            photos=[EventPhotoOut.from_model(p) for p in (e.photos or [])],
        )


class ScheduleBody(BaseModel):
    child_id: str
    name: str
    start_date: str
    interval_weeks: int = 1
    weekdays: str
    pickup_time: str
    dropoff_time: str
    pickup_location: str | None = None
    active: bool = True


class SchedulePatch(BaseModel):
    name: str | None = None
    active: bool | None = None
    start_date: str | None = None
    interval_weeks: int | None = None
    weekdays: str | None = None
    pickup_time: str | None = None
    dropoff_time: str | None = None
    pickup_location: str | None = None


class ScheduleExceptionResponse(BaseModel):
    id: str
    date: str
    kind: str
    override_pickup_at: datetime | None
    override_dropoff_at: datetime | None

    @classmethod
    def from_model(cls, x: ScheduleException) -> "ScheduleExceptionResponse":
        return cls(
            id=x.id, date=x.date, kind=x.kind,
            override_pickup_at=x.override_pickup_at,
            override_dropoff_at=x.override_dropoff_at,
        )


class ScheduleResponse(BaseModel):
    id: str
    child_id: str
    name: str
    active: bool
    start_date: str
    interval_weeks: int
    weekdays: str
    pickup_time: str
    dropoff_time: str
    pickup_location: str | None
    exceptions: list[ScheduleExceptionResponse] = Field(default_factory=list)

    @classmethod
    def from_model(cls, s: Schedule) -> "ScheduleResponse":
        return cls(
            id=s.id, child_id=s.child_id, name=s.name, active=s.active,
            start_date=s.start_date, interval_weeks=s.interval_weeks,
            weekdays=s.weekdays, pickup_time=s.pickup_time,
            dropoff_time=s.dropoff_time, pickup_location=s.pickup_location,
            exceptions=[ScheduleExceptionResponse.from_model(e) for e in (s.exceptions or [])],
        )


class ScheduleExceptionBody(BaseModel):
    date: str
    kind: str
    override_pickup_at: datetime | None = None
    override_dropoff_at: datetime | None = None


# ----- Children routes -----


@router.post("/children", status_code=status.HTTP_201_CREATED, response_model=ChildResponse)
async def create_child_route(
    body: ChildBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChildResponse:
    c = await create_child(db, user, name=body.name, dob=body.dob)
    return ChildResponse.from_model(c)


@router.get("/children", response_model=list[ChildResponse])
async def list_children_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChildResponse]:
    return [ChildResponse.from_model(c) for c in await list_children(db, user)]


@router.patch("/children/{child_id}", response_model=ChildResponse)
async def update_child_route(
    child_id: str, body: ChildBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChildResponse:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    updated = await update_child(db, child, name=body.name, dob=body.dob)
    return ChildResponse.from_model(updated)


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_child_route(
    child_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    await delete_child(db, child)


# ----- Events routes -----


@router.post("/events", status_code=status.HTTP_201_CREATED, response_model=EventResponse)
async def create_event_route(
    body: EventBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    occurred = body.occurred_at or datetime.utcnow()
    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=body.child_id,
            type=body.type,
            occurred_at=occurred,
            notes=body.notes,
            location=body.location,
            overnight=body.overnight,
            amount_cents=body.amount_cents,
            category=body.category,
            call_connected=body.call_connected,
            missed_source=body.missed_source,
        ))
    except InvalidEventData as e:
        raise HTTPException(status_code=400, detail=str(e))
    return EventResponse.from_model(evt)


@router.get("/events", response_model=list[EventResponse])
async def list_events_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    child_id: str | None = Query(default=None),
    type: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[EventResponse]:
    rows = await list_events(
        db, user, child_id=child_id, type=type,
        from_dt=from_dt, to_dt=to_dt, limit=limit, offset=offset,
    )
    return [EventResponse.from_model(e) for e in rows]


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event_route(
    event_id: str, body: EventPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    patch = body.model_dump(exclude_unset=True)
    updated = await update_event(db, evt, **patch)
    return EventResponse.from_model(updated)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_route(
    event_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    await delete_event(db, evt)


@router.post("/events/{event_id}/photos")
async def upload_event_photo_route(
    event_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    photo = await save_event_photo(db, event_id, file)
    return EventPhotoOut.from_model(photo).model_dump()


@router.delete(
    "/events/{event_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_event_photo_route(
    event_id: str, photo_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    photo = await db.get(EventPhoto, photo_id)
    if photo is None or photo.event_id != event_id:
        raise HTTPException(status_code=404, detail="photo_not_found")
    await delete_event_photo(db, photo)


# ----- Schedule routes -----

# NOTE: /schedules/refresh-missed and /schedules/exceptions/{id} must come
# before /schedules/{schedule_id} to avoid FastAPI treating "refresh-missed"
# and "exceptions" as a schedule_id path param.


@router.post("/schedules/refresh-missed")
async def refresh_missed_route(
    child_id: str = Query(...),
    up_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    if up_to is None:
        up_to_dt = datetime.utcnow()
    else:
        try:
            up_to_dt = datetime.fromisoformat(up_to + "T23:59:59")
        except ValueError:
            raise HTTPException(status_code=400, detail="up_to_must_be_YYYY-MM-DD")
    new_rows = await refresh_missed(db, user, child_id, up_to=up_to_dt)
    return {"new_rows": new_rows}


@router.delete(
    "/schedules/exceptions/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_exception_route(
    exception_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ex = await db.get(ScheduleException, exception_id)
    if ex is None:
        raise HTTPException(status_code=404, detail="exception_not_found")
    sched = await get_schedule(db, user, ex.schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="exception_not_found")
    await delete_schedule_exception(db, ex)


@router.post("/schedules", status_code=status.HTTP_201_CREATED, response_model=ScheduleResponse)
async def create_schedule_route(
    body: ScheduleBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    try:
        sched = await create_schedule(db, user, CreateScheduleInput(
            child_id=body.child_id, name=body.name,
            start_date=body.start_date, interval_weeks=body.interval_weeks,
            weekdays=body.weekdays,
            pickup_time=body.pickup_time, dropoff_time=body.dropoff_time,
            pickup_location=body.pickup_location, active=body.active,
        ))
    except InvalidScheduleData as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScheduleResponse.from_model(sched)


@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    child_id: str | None = Query(default=None),
) -> list[ScheduleResponse]:
    rows = await list_schedules(db, user, child_id=child_id)
    return [ScheduleResponse.from_model(s) for s in rows]


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_route(
    schedule_id: str, body: SchedulePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    sched = await get_schedule(db, user, schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    patch = body.model_dump(exclude_unset=True)
    updated = await update_schedule(db, sched, **patch)
    return ScheduleResponse.from_model(updated)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_route(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    sched = await get_schedule(db, user, schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    await delete_schedule(db, sched)


@router.post(
    "/schedules/{schedule_id}/exceptions",
    status_code=status.HTTP_201_CREATED,
    response_model=ScheduleExceptionResponse,
)
async def add_exception_route(
    schedule_id: str, body: ScheduleExceptionBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleExceptionResponse:
    sched = await get_schedule(db, user, schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    try:
        ex = await add_schedule_exception(
            db, sched,
            date=body.date, kind=body.kind,
            override_pickup_at=body.override_pickup_at,
            override_dropoff_at=body.override_dropoff_at,
        )
    except InvalidScheduleData as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScheduleExceptionResponse.from_model(ex)


# ----- Status / summary / export routes -----


@router.get("/status")
async def status_route(
    child_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return await compute_status(db, user, child_id, now=datetime.utcnow())


@router.get("/summary")
async def summary_route(
    child_id: str = Query(...),
    month: str = Query(..., description="YYYY-MM"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    try:
        year_s, month_s = month.split("-")
        y, m = int(year_s), int(month_s)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="month_must_be_YYYY-MM")
    return await compute_summary(db, user, child_id, year=y, month=m)


@router.get("/export")
async def export_route(
    child_id: str = Query(...),
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    format: str = Query(default="pdf", pattern="^(pdf|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    if format == "csv":
        data = await export_csv(db, user, child_id=child_id, from_dt=from_dt, to_dt=to_dt)
        return Response(
            content=data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="custody-{child.name}.csv"'},
        )
    data = await export_pdf(db, user, child_id=child_id, from_dt=from_dt, to_dt=to_dt)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="custody-{child.name}.pdf"'},
    )
