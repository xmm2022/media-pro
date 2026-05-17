from fastapi import APIRouter, HTTPException, Request, status

from gateway.schemas import DriveAccountCreate, DriveAccountRead, UserCreate, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request) -> UserRead:
    users: list[UserRead] = request.app.state.admin_users
    user = UserRead(id=len(users) + 1, username=payload.username, status=payload.status)
    users.append(user)
    return user


@router.post("/drives", response_model=DriveAccountRead, status_code=status.HTTP_201_CREATED)
def create_drive(payload: DriveAccountCreate, request: Request) -> DriveAccountRead:
    users: list[UserRead] = request.app.state.admin_users
    drives: list[DriveAccountRead] = request.app.state.admin_drives

    if not any(user.id == payload.user_id for user in users):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    preview = f"{payload.cookie[:5]}..."
    drive = DriveAccountRead(
        id=len(drives) + 1,
        user_id=payload.user_id,
        drive_type=payload.drive_type,
        root_dir=payload.root_dir,
        share_pool_enabled=payload.share_pool_enabled,
        cookie_preview=preview,
    )
    drives.append(drive)
    return drive
