from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.auth_service import authenticate_user, create_access_token, decode_token
from app.models.user import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
templates = Jinja2Templates(directory="app/templates")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter_by(username=username, is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# ── Admin session helpers ─────────────────────────────────────────────────────

def _session_cookie_name() -> str:
    return "crm_session"


def set_session(response, username: str) -> None:
    from itsdangerous import URLSafeTimedSerializer
    from app.config import get_settings
    s = URLSafeTimedSerializer(get_settings().SECRET_KEY)
    token = s.dumps(username, salt="admin-session")
    response.set_cookie(
        _session_cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        max_age=28800,
    )


def get_session_user(request: Request) -> str | None:
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
    from app.config import get_settings
    token = request.cookies.get(_session_cookie_name())
    if not token:
        return None
    s = URLSafeTimedSerializer(get_settings().SECRET_KEY)
    try:
        return s.loads(token, salt="admin-session", max_age=28800)
    except (BadSignature, SignatureExpired):
        return None


def require_session(request: Request):
    user = get_session_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )
    return user


# ── Admin login / logout routes ───────────────────────────────────────────────

@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/admin/login")
async def admin_login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    user = authenticate_user(db, str(form.get("username", "")), str(form.get("password", "")))
    if not user:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid username or password"}, status_code=401
        )
    response = RedirectResponse(url="/admin/", status_code=303)
    set_session(response, user.username)
    return response


@router.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(_session_cookie_name())
    return response
