from fastapi import APIRouter, Depends, HTTPException, status
from godata.repos import TripRepo
from godata.models import Trip, User
from ..schemas import TripIn, TripOut
from ..auth import require_user

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _serialize(t: Trip) -> TripOut:
    return TripOut(
        id=t.id,
        name=t.name,
        from_city=t.from_city,
        to_city=t.to_city,
        date=t.date,
        capacity=t.capacity,
        weight=t.weight,
        cap_desc=t.cap_desc,
        wa=t.wa,
        owner_id=t.owner_id,
        created_at=t.created_at,
    )


@router.get("", response_model=list[TripOut])
def list_trips() -> list[TripOut]:
    return [_serialize(t) for t in TripRepo.list_all()]


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(body: TripIn, user: User = Depends(require_user)) -> TripOut:
    trip = TripRepo.create(owner_id=user.id, **body.model_dump())
    return _serialize(trip)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, user: User = Depends(require_user)) -> None:
    if not TripRepo.delete(trip_id, user.id):
        raise HTTPException(status_code=404, detail="Trajet introuvable ou non autorisé")
