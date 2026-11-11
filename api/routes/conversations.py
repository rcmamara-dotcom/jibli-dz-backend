import logging
from fastapi import APIRouter, Depends, HTTPException, status
from godata.repos import ConversationRepo, TripRepo, ParcelRepo
from godata.models import User, Conversation, Message
from ..schemas import ConversationStartIn, ConversationOut, MessageIn, MessageOut
from ..auth import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


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


def _serialize_conversation(conv: Conversation, user_id: int) -> ConversationOut:
    is_initiator = conv.initiator_id == user_id
    other = conv.recipient if is_initiator else conv.initiator
    messages = ConversationRepo.list_messages(conv.id)
    last = messages[-1] if messages else None
    unread = sum(
        1 for m in messages if not m.is_read and m.sender_id != user_id
    )
    return ConversationOut(
        id=conv.id,
        other_user_id=other.id,
        other_user_name=other.name,
        trip_id=conv.trip_id,
        parcel_id=conv.parcel_id,
        last_message=last.content if last else None,
        last_message_at=last.created_at if last else None,
        unread_count=unread,
        created_at=conv.created_at,
    )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def start_conversation(body: ConversationStartIn, user: User = Depends(require_user)) -> ConversationOut:
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
    return _serialize_conversation(conv, user.id)


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(require_user)) -> list[ConversationOut]:
    convs = ConversationRepo.list_for_user(user.id)
    return [_serialize_conversation(c, user.id) for c in convs]


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
def send_message(conv_id: int, body: MessageIn, user: User = Depends(require_user)) -> MessageOut:
    conv = ConversationRepo.get_by_id(conv_id)
    if not conv or (conv.initiator_id != user.id and conv.recipient_id != user.id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    msg = ConversationRepo.send_message(conv_id, user.id, body.content)
    return _serialize_message(msg, user.id)
