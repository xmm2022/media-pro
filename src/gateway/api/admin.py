from fastapi import APIRouter, status

from gateway.schemas import DriveAccountCreate, DriveAccountRead, UserCreate, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"])

_users: list[UserRead] = []
_drives: list[DriveAccountRead] = []


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate) -> UserRead:
    user = UserRead(id=len(_users) + 1, username=payload.username, status=payload.status)
    _users.append(user)
    return user


@router.post("/drives", response_model=DriveAccountRead, status_code=status.HTTP_201_CREATED)
def create_drive(payload: DriveAccountCreate) -> DriveAccountRead:
    preview = f"{payload.cookie[:5]}..."
    drive = DriveAccountRead(
        id=len(_drives) + 1,
        user_id=payload.user_id,
        drive_type=payload.drive_type,
        root_dir=payload.root_dir,
        share_pool_enabled=payload.share_pool_enabled,
        cookie_preview=preview,
    )
    _drives.append(drive)
    return drive
