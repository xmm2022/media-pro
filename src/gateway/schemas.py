from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    status: str = "active"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    drive_type: str
    root_dir: str
    share_pool_enabled: bool
    cookie_preview: str
