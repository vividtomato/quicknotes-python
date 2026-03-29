import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import case
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    authenticate_user,
    get_current_user_optional,
    get_user_by_username,
    hash_password,
    require_user,
)
from app.database import Base, apply_sqlite_migrations, engine, get_db
from app.models import Note, Tag, User

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "change-me-in-production-use-env",
)  # noqa: S105

app = FastAPI(title="Quick Notes")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _redirect_home(return_tag: str, db: Session, user: User) -> str:
    t = return_tag.strip()
    if t.isdigit():
        tid = int(t)
        if db.query(Tag).filter(Tag.id == tid, Tag.user_id == user.id).first():
            return f"/?tag={tid}"
    return "/"


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    apply_sqlite_migrations()


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    tag: int | None = Query(None),
):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    filter_tag_id: int | None = None
    if tag is not None:
        if db.query(Tag).filter(Tag.id == tag, Tag.user_id == user.id).first():
            filter_tag_id = tag

    q = (
        db.query(Note)
        .outerjoin(Tag, Note.tag_id == Tag.id)
        .filter(Note.user_id == user.id)
    )
    if filter_tag_id is not None:
        q = q.filter(Note.tag_id == filter_tag_id)

    notes = (
        q.order_by(
            case((Note.tag_id.is_(None), 1), else_=0),
            Tag.name.asc(),
            Note.created_at.desc(),
        )
        .all()
    )
    tags = (
        db.query(Tag).filter(Tag.user_id == user.id).order_by(Tag.name.asc()).all()
    )
    return templates.TemplateResponse(
        request,
        "wall.html",
        {
            "user": user,
            "notes": notes,
            "tags": tags,
            "filter_tag_id": filter_tag_id,
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "login.html", {"error": None}
    )


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(db, username.strip(), password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверное имя или пароль"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "register.html", {"error": None}
    )


@app.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
):
    name = username.strip()
    if len(name) < 2:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Имя пользователя слишком короткое"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if len(password) < 4:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Пароль слишком короткий"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if get_user_by_username(db, name):
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Такой пользователь уже есть"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    user = User(username=name, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/tags")
def create_tag(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    name: str = Form(...),
    return_tag: str = Form(""),
):
    label = name.strip()
    if not label or len(label) > 128:
        return RedirectResponse(
            _redirect_home(return_tag, db, user), status_code=status.HTTP_303_SEE_OTHER
        )
    if not db.query(Tag).filter(Tag.user_id == user.id, Tag.name == label).first():
        db.add(Tag(user_id=user.id, name=label))
        db.commit()
    return RedirectResponse(
        _redirect_home(return_tag, db, user), status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/tags/{tag_id}/delete")
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    return_tag: str = Form(""),
):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == user.id).first()
    if tag:
        db.delete(tag)
        db.commit()
    loc = _redirect_home(return_tag, db, user)
    if return_tag.strip() == str(tag_id):
        loc = "/"
    return RedirectResponse(loc, status_code=status.HTTP_303_SEE_OTHER)


@app.post("/notes", response_class=HTMLResponse)
def create_note(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    content: str = Form(...),
    tag_id: str = Form(""),
    new_tag: str = Form(""),
    return_tag: str = Form(""),
):
    text = content.strip()
    if not text:
        return RedirectResponse(
            _redirect_home(return_tag, db, user), status_code=status.HTTP_303_SEE_OTHER
        )

    tag_id_int: int | None = None
    new_label = new_tag.strip()
    if new_label:
        if len(new_label) > 128:
            return RedirectResponse(
                _redirect_home(return_tag, db, user),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        existing = (
            db.query(Tag).filter(Tag.user_id == user.id, Tag.name == new_label).first()
        )
        if existing:
            tag_id_int = existing.id
        else:
            t = Tag(user_id=user.id, name=new_label)
            db.add(t)
            db.commit()
            db.refresh(t)
            tag_id_int = t.id
    elif tag_id.strip().isdigit():
        cand = int(tag_id)
        if db.query(Tag).filter(Tag.id == cand, Tag.user_id == user.id).first():
            tag_id_int = cand

    note = Note(user_id=user.id, content=text, tag_id=tag_id_int)
    db.add(note)
    db.commit()
    return RedirectResponse(
        _redirect_home(return_tag, db, user), status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/notes/{note_id}/tag")
def set_note_tag(
    note_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    tag_id: str = Form(""),
    return_tag: str = Form(""),
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == user.id).first()
    if note:
        tid: int | None = None
        if tag_id.strip().isdigit():
            cand = int(tag_id)
            if db.query(Tag).filter(Tag.id == cand, Tag.user_id == user.id).first():
                tid = cand
        note.tag_id = tid
        db.commit()
    return RedirectResponse(
        _redirect_home(return_tag, db, user), status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/notes/{note_id}/delete")
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    return_tag: str = Form(""),
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == user.id).first()
    if note:
        db.delete(note)
        db.commit()
    return RedirectResponse(
        _redirect_home(return_tag, db, user), status_code=status.HTTP_303_SEE_OTHER
    )
