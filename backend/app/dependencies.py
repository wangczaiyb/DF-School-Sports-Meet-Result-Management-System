from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User, UserStatus
from .security import decode_access_token


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    try:
        payload = decode_access_token(credentials.credentials)
        user = db.get(User, int(payload["sub"]))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录状态已失效") from exc
    if not user or user.status != UserStatus.ACTIVE or user.token_version != payload.get("ver"):
        raise HTTPException(status_code=401, detail="账号已冻结或登录状态已失效")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="无权执行此操作")
        return user

    return dependency


developer_only = require_roles(Role.DEVELOPER)
business_admin = require_roles(Role.DEVELOPER, Role.SPORTS_TEACHER)
manager_only = require_roles(Role.DEVELOPER, Role.SPORTS_TEACHER, Role.REFEREE, Role.SCORER, Role.REFEREE_SCORER)
student_only = require_roles(Role.STUDENT)
