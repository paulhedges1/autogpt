from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.note import Note
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.note import NoteCreate, NoteRead

router = APIRouter()


@router.get("/", response_model=List[NoteRead])
def list_notes(
    contact_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Note)
    if contact_id is not None:
        q = q.filter_by(contact_id=contact_id)
    return q.offset(skip).limit(limit).all()


@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    note = Note(**payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    note = db.query(Note).filter_by(id=note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
