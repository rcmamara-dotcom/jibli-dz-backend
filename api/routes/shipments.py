import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from godata.models import User, Shipment, SHIPMENT_STEPS, SHIPMENT_CANCELLED
from godata.repos import ShipmentRepo, TripRepo, UserRepo
from ..schemas import ShipmentIn, ShipmentStatusIn, ShipmentOut, ShipmentEventOut
from ..auth import require_user
from ..scheduler import _send
from ..limiter import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shipments", tags=["shipments"])

STEP_LABELS = {
    "deposited": "Commande déposée",
    "accepted": "Acceptée par le voyageur",
    "picked_up": "Colis récupéré",
    "in_transit": "En route",
    "arrived": "Arrivé à destination",
    "delivered": "Livré",
    SHIPMENT_CANCELLED: "Annulé",
}
# Jusqu'où chacun peut annuler (après la remise du colis, plus d'annulation)
CANCELLABLE = ("deposited", "accepted")


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.name or user.email.split("@")[0]


def _serialize(s: Shipment, user: User) -> ShipmentOut:
    is_sender = s.sender_id == user.id
    other = UserRepo.get_by_id(s.carrier_id if is_sender else s.sender_id)
    return ShipmentOut(
        id=s.id,
        trip_id=s.trip_id,
        from_city=s.from_city,
        to_city=s.to_city,
        trip_date=s.trip_date,
        description=s.description,
        status=s.status,
        role="sender" if is_sender else "carrier",
        counterpart_name=_display_name(other),
        events=[ShipmentEventOut(status=e.status, created_at=e.created_at) for e in ShipmentRepo.events(s.id)],
        created_at=s.created_at,
    )


def _notify(shipment: Shipment, to_user_id: int) -> None:
    user = UserRepo.get_by_id(to_user_id)
    if not user:
        return
    label = STEP_LABELS.get(shipment.status, shipment.status)
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">📍 Suivi de ton envoi</h2>
      <p style="color:#6b7280;line-height:1.6">
        Ton envoi <strong>{shipment.from_city} → {shipment.to_city}</strong> est passé à l'étape :
      </p>
      <p style="font-size:20px;font-weight:700;color:#0f5c32">{label}</p>
      <p style="color:#6b7280;font-size:13px">Retrouve toutes les étapes dans « Mes envois » sur JIBLI DZ.</p>
    </div>
    """
    _send(user.email, f"📍 {label} — {shipment.from_city} → {shipment.to_city}", html)


def _get_mine(shipment_id: int, user: User) -> Shipment:
    s = ShipmentRepo.get_by_id(shipment_id)
    if not s or user.id not in (s.sender_id, s.carrier_id):
        raise HTTPException(status_code=404, detail="Envoi introuvable")
    return s


@router.get("", response_model=list[ShipmentOut])
def list_shipments(user: User = Depends(require_user)) -> list[ShipmentOut]:
    return [_serialize(s, user) for s in ShipmentRepo.list_for_user(user.id)]


@router.post("", response_model=ShipmentOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/day")
def create_shipment(request: Request, body: ShipmentIn, bg: BackgroundTasks, user: User = Depends(require_user)) -> ShipmentOut:
    trip = TripRepo.get_by_id(body.trip_id)
    if not trip or not trip.owner_id:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    if trip.owner_id == user.id:
        raise HTTPException(status_code=400, detail="C'est ton propre trajet")
    s = ShipmentRepo.create(trip, user.id, body.description)
    log.info("Shipment créé: id=%s trip=%s sender=%s", s.id, trip.id, user.id)
    bg.add_task(_notify, s, s.carrier_id)
    return _serialize(s, user)


@router.post("/{shipment_id}/status", response_model=ShipmentOut)
def update_status(shipment_id: int, body: ShipmentStatusIn, bg: BackgroundTasks, user: User = Depends(require_user)) -> ShipmentOut:
    s = _get_mine(shipment_id, user)
    new = body.status
    if s.status in ("delivered", SHIPMENT_CANCELLED):
        raise HTTPException(status_code=400, detail="Cet envoi est terminé")

    if new == SHIPMENT_CANCELLED:
        if s.status not in CANCELLABLE:
            raise HTTPException(status_code=400, detail="Le colis a déjà été remis au voyageur")
    else:
        # Seul le voyageur fait avancer, et uniquement vers l'étape suivante
        if user.id != s.carrier_id:
            raise HTTPException(status_code=403, detail="Seul le voyageur met à jour les étapes")
        if new not in SHIPMENT_STEPS or SHIPMENT_STEPS.index(new) != SHIPMENT_STEPS.index(s.status) + 1:
            raise HTTPException(status_code=400, detail="Étape invalide")

    s = ShipmentRepo.set_status(s, new)
    log.info("Shipment %s → %s (par user_id=%s)", s.id, new, user.id)
    bg.add_task(_notify, s, s.carrier_id if user.id == s.sender_id else s.sender_id)
    return _serialize(s, user)
