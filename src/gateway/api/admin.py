from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gateway.db import get_session, init_schema
from gateway.models import PlaybackRecord, User, UserDriveAccount
from gateway.schemas import DriveAccountCreate, DriveAccountRead, UserCreate, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def admin_stats(request: Request, session: Session = Depends(get_session)) -> dict[str, int]:
    init_schema(request.app.state.engine)
    routes = session.scalars(select(PlaybackRecord.route)).all()
    normalized_routes = [
        route.value if hasattr(route, "value") else str(route) for route in routes
    ]
    return summarize_routes(normalized_routes)


def summarize_routes(routes: list[str]) -> dict[str, int]:
    summary = {"self": 0, "pool": 0, "source_copy": 0, "source_stream": 0}
    for route in routes:
        summary[route] = summary.get(route, 0) + 1
    return summary


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> UserRead:
    user = User(username=payload.username, status=payload.status)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from None
    session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/drives", response_model=DriveAccountRead, status_code=status.HTTP_201_CREATED)
def create_drive(
    payload: DriveAccountCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveAccountRead:
    if session.get(User, payload.user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    drive = UserDriveAccount(
        user_id=payload.user_id,
        drive_type=payload.drive_type,
        cookie_encrypted=request.app.state.cookie_cipher.encrypt(payload.cookie),
        root_dir=payload.root_dir,
        share_pool_enabled=payload.share_pool_enabled,
    )
    session.add(drive)
    session.commit()
    session.refresh(drive)
    return DriveAccountRead(
        id=drive.id,
        user_id=payload.user_id,
        drive_type=payload.drive_type,
        root_dir=payload.root_dir,
        share_pool_enabled=payload.share_pool_enabled,
        cookie_preview=f"{payload.cookie[:5]}...",
    )
