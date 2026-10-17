from passlib.context import CryptContext
from starlette.middleware.sessions import SessionMiddleware

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def mount_session(app, secret_key: str) -> None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        session_cookie="entitle_session",
        same_site="lax",
        https_only=False,
    )
