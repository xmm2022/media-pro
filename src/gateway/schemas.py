from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    status: str = "active"


class UserRead(BaseModel):
    id: int
    username: str
    status: str


class DriveAccountCreate(BaseModel):
    user_id: int
    drive_type: str
    cookie: str
    root_dir: str
    share_pool_enabled: bool = False


class DriveAccountRead(BaseModel):
    id: int
    user_id: int
    drive_type: str
    root_dir: str
    share_pool_enabled: bool
    cookie_preview: str
