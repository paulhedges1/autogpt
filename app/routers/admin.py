from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.contact import Contact, PipelineStage
from app.models.deal import Deal
from app.models.note import Note
from app.models.order import Order
from app.routers.auth import get_session_user, require_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

STAGES = list(PipelineStage)


def _ctx(request: Request, **kwargs):
    return {"request": request, "current_user": get_session_user(request), **kwargs}


# ── Auth check dependency ─────────────────────────────────────────────────────

def _auth(request: Request, _=Depends(require_session)):
    pass


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), _=Depends(require_session)):
    counts = {
        "contacts": db.query(Contact).count(),
        "orders": db.query(Order).count(),
        "deals": db.query(Deal).count(),
        "notes": db.query(Note).count(),
    }
    recent_contacts = db.query(Contact).order_by(Contact.created_at.desc()).limit(5).all()
    recent_orders = db.query(Order).order_by(Order.created_at.desc()).limit(5).all()
    return templates.TemplateResponse(
        "dashboard.html",
        _ctx(request, counts=counts, recent_contacts=recent_contacts, recent_orders=recent_orders),
    )


# ── Contacts ─────────────────────────────────────────────────────────────────

@router.get("/contacts", response_class=HTMLResponse)
def contacts_list(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db),
    _=Depends(require_session),
):
    q = db.query(Contact)
    if search:
        q = q.filter(
            Contact.email.contains(search)
            | Contact.full_name.contains(search)
            | Contact.company.contains(search)
        )
    contacts = q.order_by(Contact.created_at.desc()).all()
    return templates.TemplateResponse(
        "contacts/list.html", _ctx(request, contacts=contacts, search=search)
    )


@router.get("/contacts/new", response_class=HTMLResponse)
def contact_new(request: Request, _=Depends(require_session)):
    return templates.TemplateResponse(
        "contacts/form.html", _ctx(request, contact=None, stages=STAGES, error=None)
    )


@router.post("/contacts")
async def contact_create(request: Request, db: Session = Depends(get_db), _=Depends(require_session)):
    form = await request.form()
    contact = Contact(
        email=str(form.get("email", "")).strip(),
        full_name=str(form.get("full_name", "")).strip() or None,
        phone=str(form.get("phone", "")).strip() or None,
        company=str(form.get("company", "")).strip() or None,
        stage=PipelineStage(form.get("stage", "lead")),
    )
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "contacts/form.html",
            _ctx(request, contact=None, stages=STAGES, error="Email already exists"),
            status_code=400,
        )
    return RedirectResponse(url=f"/admin/contacts/{contact.id}", status_code=303)


@router.get("/contacts/{contact_id}", response_class=HTMLResponse)
def contact_detail(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(require_session),
):
    contact = db.query(Contact).filter_by(id=contact_id).first()
    if not contact:
        return RedirectResponse("/admin/contacts", status_code=303)
    return templates.TemplateResponse(
        "contacts/detail.html",
        _ctx(request, contact=contact, stages=STAGES),
    )


@router.post("/contacts/{contact_id}")
async def contact_update(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(require_session),
):
    contact = db.query(Contact).filter_by(id=contact_id).first()
    if not contact:
        return RedirectResponse("/admin/contacts", status_code=303)
    form = await request.form()
    contact.full_name = str(form.get("full_name", "")).strip() or None
    contact.phone = str(form.get("phone", "")).strip() or None
    contact.company = str(form.get("company", "")).strip() or None
    contact.stage = PipelineStage(form.get("stage", contact.stage.value))
    db.commit()
    return RedirectResponse(url=f"/admin/contacts/{contact_id}", status_code=303)


@router.post("/contacts/{contact_id}/delete")
def contact_delete(
    contact_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_session),
):
    contact = db.query(Contact).filter_by(id=contact_id).first()
    if contact:
        db.delete(contact)
        db.commit()
    return RedirectResponse("/admin/contacts", status_code=303)


# ── Notes ────────────────────────────────────────────────────────────────────

@router.post("/contacts/{contact_id}/notes")
async def note_create(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(require_session),
):
    form = await request.form()
    note = Note(
        contact_id=contact_id,
        body=str(form.get("body", "")).strip(),
        author=str(form.get("author", "")).strip() or None,
    )
    db.add(note)
    db.commit()
    return RedirectResponse(url=f"/admin/contacts/{contact_id}", status_code=303)


@router.post("/notes/{note_id}/delete")
def note_delete(note_id: int, db: Session = Depends(get_db), _=Depends(require_session)):
    note = db.query(Note).filter_by(id=note_id).first()
    contact_id = note.contact_id if note else None
    if note:
        db.delete(note)
        db.commit()
    return RedirectResponse(url=f"/admin/contacts/{contact_id}" if contact_id else "/admin/contacts", status_code=303)


# ── Deals / Pipeline ─────────────────────────────────────────────────────────

@router.get("/deals/pipeline", response_class=HTMLResponse)
def pipeline(request: Request, db: Session = Depends(get_db), _=Depends(require_session)):
    deals = db.query(Deal).all()
    by_stage = {stage: [] for stage in STAGES}
    for deal in deals:
        by_stage[deal.stage].append(deal)
    return templates.TemplateResponse(
        "deals/pipeline.html", _ctx(request, by_stage=by_stage, stages=STAGES)
    )


@router.get("/deals/new", response_class=HTMLResponse)
def deal_new(request: Request, db: Session = Depends(get_db), _=Depends(require_session)):
    contacts = db.query(Contact).order_by(Contact.full_name).all()
    return templates.TemplateResponse(
        "deals/form.html", _ctx(request, deal=None, contacts=contacts, stages=STAGES, error=None)
    )


@router.post("/deals")
async def deal_create(request: Request, db: Session = Depends(get_db), _=Depends(require_session)):
    form = await request.form()
    deal = Deal(
        contact_id=int(form["contact_id"]),
        title=str(form.get("title", "")).strip(),
        value=float(form.get("value") or 0),
        stage=PipelineStage(form.get("stage", "lead")),
    )
    db.add(deal)
    db.commit()
    return RedirectResponse("/admin/deals/pipeline", status_code=303)


@router.post("/deals/{deal_id}")
async def deal_update(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(require_session),
):
    deal = db.query(Deal).filter_by(id=deal_id).first()
    if deal:
        form = await request.form()
        deal.title = str(form.get("title", deal.title)).strip()
        deal.value = float(form.get("value") or deal.value)
        deal.stage = PipelineStage(form.get("stage", deal.stage.value))
        db.commit()
    return RedirectResponse("/admin/deals/pipeline", status_code=303)


@router.post("/deals/{deal_id}/delete")
def deal_delete(deal_id: int, db: Session = Depends(get_db), _=Depends(require_session)):
    deal = db.query(Deal).filter_by(id=deal_id).first()
    if deal:
        db.delete(deal)
        db.commit()
    return RedirectResponse("/admin/deals/pipeline", status_code=303)


# ── Orders ───────────────────────────────────────────────────────────────────

@router.get("/orders", response_class=HTMLResponse)
def orders_list(request: Request, db: Session = Depends(get_db), _=Depends(require_session)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return templates.TemplateResponse("orders/list.html", _ctx(request, orders=orders))
