import logging
import os
from html import escape
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from godata.repos import ConversationRepo, TripRepo, ParcelRepo, UserReviewRepo
from godata.models import User, Conversation, Message
from ..schemas import ConversationStartIn, ConversationOut, MessageIn, MessageOut
from ..auth import require_user
from ..scheduler import _send

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversations"])
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://jiblidz.com")


def _notify_recipient(background: BackgroundTasks, conv: Conversation, sender: User, content: str) -> None:
    """E-mail au destinataire, seulement pour le premier message non lu (pas un e-mail par message)."""
    recipient = conv.recipient if conv.initiator_id == sender.id else conv.initiator
    if not recipient.notify_messages or not recipient.email_verified:
        return
    if ConversationRepo.unread_in_conversation(conv.id, recipient.id) != 1:
        return
    sender_name = escape(sender.name or "Un utilisateur")
    preview = escape(content if len(content) <= 300 else content[:300] + "…").replace("\n", "<br>")
    link = f"{PUBLIC_URL}/?messages={conv.id}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">💬 Nouveau message de {sender_name}</h2>
      <div style="background:#f6f8f5;border-left:4px solid #22c55e;border-radius:8px;padding:14px 16px;margin:20px 0;color:#111827;line-height:1.5">
        {preview}
      </div>
      <a href="{link}" style="display:inline-block;background:#1a6b3c;color:white;text-decoration:none;font-weight:600;padding:12px 24px;border-radius:8px">
        Répondre sur JIBLI DZ
      </a>
      <p style="color:#6b7280;font-size:12px;margin-top:32px">
        Tu reçois cet e-mail car quelqu'un t'a écrit sur JIBLI DZ.
        Pour ne plus recevoir ces e-mails : Mon compte → Notifications.
      </p>
    </div>
    """
    background.add_task(_send, recipient.email, f"💬 Nouveau message de {sender.name or 'un utilisateur'} — JIBLI DZ", html)


def _serialize_message(msg: Message, _: int) -> MessageOut:
    sender = msg.sender
    return MessageOut(
        id=msg.id,
        sender_id=sender.id,
        sender_name=sender.name,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


def _serialize_conversation(conv: Conversation, user_id: int, ratings: dict | None = None) -> ConversationOut:
    is_initiator = conv.initiator_id == user_id
    other = conv.recipient if is_initiator else conv.initiator
    messages = ConversationRepo.list_messages(conv.id)
    last = messages[-1] if messages else None
    unread = sum(
        1 for m in messages if not m.is_read and m.sender_id != user_id
    )
    rating = (ratings if ratings is not None else UserReviewRepo.bulk([other.id])).get(other.id)
    return ConversationOut(
        id=conv.id,
        other_user_id=other.id,
        other_user_name=other.name,
        other_user_rating=rating["avg"] if rating else None,
        other_user_review_count=rating["count"] if rating else 0,
        trip_id=conv.trip_id,
        parcel_id=conv.parcel_id,
        last_message=last.content if last else None,
        last_message_at=last.created_at if last else None,
        unread_count=unread,
        created_at=conv.created_at,
    )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def start_conversation(
    body: ConversationStartIn, background: BackgroundTasks, user: User = Depends(require_user)
) -> ConversationOut:
    if not body.trip_id and not body.parcel_id:
        raise HTTPException(status_code=400, detail="trip_id ou parcel_id requis")

    if body.trip_id:
        trip = TripRepo.get_by_id(body.trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trajet introuvable")
        if trip.owner_id == user.id:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous envoyer un message")
        conv, _ = ConversationRepo.get_or_create_for_trip(body.trip_id, user.id, trip.owner_id)
    else:
        parcel = ParcelRepo.get_by_id(body.parcel_id)
        if not parcel:
            raise HTTPException(status_code=404, detail="Colis introuvable")
        if parcel.owner_id == user.id:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous envoyer un message")
        conv, _ = ConversationRepo.get_or_create_for_parcel(body.parcel_id, user.id, parcel.owner_id)

    ConversationRepo.send_message(conv.id, user.id, body.message)
    _notify_recipient(background, conv, user, body.message)
    return _serialize_conversation(conv, user.id)


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(require_user)) -> list[ConversationOut]:
    convs = ConversationRepo.list_for_user(user.id)
    others = {c.recipient_id if c.initiator_id == user.id else c.initiator_id for c in convs}
    ratings = UserReviewRepo.bulk(list(others))
    return [_serialize_conversation(c, user.id, ratings) for c in convs]


@router.get("/unread", response_model=dict)
def unread_count(user: User = Depends(require_user)) -> dict:
    return {"count": ConversationRepo.unread_count(user.id)}


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
def get_messages(conv_id: int, user: User = Depends(require_user)) -> list[MessageOut]:
    conv = ConversationRepo.get_by_id(conv_id)
    if not conv or (conv.initiator_id != user.id and conv.recipient_id != user.id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    ConversationRepo.mark_read(conv_id, user.id)
    messages = ConversationRepo.list_messages(conv_id)
    return [_serialize_message(m, user.id) for m in messages]


@router.post("/{conv_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    conv_id: int, body: MessageIn, background: BackgroundTasks, user: User = Depends(require_user)
) -> MessageOut:
    conv = ConversationRepo.get_by_id(conv_id)
    if not conv or (conv.initiator_id != user.id and conv.recipient_id != user.id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    msg = ConversationRepo.send_message(conv_id, user.id, body.content)
    _notify_recipient(background, conv, user, body.content)
    return _serialize_message(msg, user.id)
