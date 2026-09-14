from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReportChatMessage, User
from app.schemas import ParameterItem, ReportChatIn, ReportChatMessageOut, ReportChatOut
from app.security import get_current_user
from app.services.reports_service import PARAMETERS_CATALOG, ask_reports_ai

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/parameters", response_model=List[ParameterItem])
def list_parameters(_: User = Depends(get_current_user)):
    return PARAMETERS_CATALOG


@router.get("/chat", response_model=List[ReportChatMessageOut])
def chat_history(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (
        db.query(ReportChatMessage)
        .order_by(ReportChatMessage.id.asc())
        .limit(100)
        .all()
    )
    return rows


@router.delete("/chat")
def clear_chat(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    db.query(ReportChatMessage).delete()
    db.commit()
    return {"ok": True}


@router.post("/chat", response_model=ReportChatOut)
def chat(
    payload: ReportChatIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    msg = payload.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Mensagem vazia")
    try:
        reply = ask_reports_ai(db, msg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.add(ReportChatMessage(role="user", content=msg))
    asst = ReportChatMessage(role="assistant", content=reply or "Sem resposta.")
    db.add(asst)
    db.commit()
    rows = (
        db.query(ReportChatMessage)
        .order_by(ReportChatMessage.id.asc())
        .limit(100)
        .all()
    )
    return ReportChatOut(reply=asst.content, messages=rows)
