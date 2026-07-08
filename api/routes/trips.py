import logging
from fastapi import APIRouter, Depends, HTTPException, status
from godata.repos import TripRepo, ReviewRepo
from godata.models import Trip, User
from ..schemas import TripIn, TripOut
from ..auth import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trips", tags=["trips"])


def _serialize(t: Trip, ratings: dict | None = None) -> TripOut:
    rating_info = (ratings or {}).get(t.owner_id) if t.owner_id else None
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
        avg_rating=rating_info["avg"] if rating_info else None,
        review_count=rating_info["count"] if rating_info else 0,
    )


@router.get("", response_model=list[TripOut])
def list_trips() -> list[TripOut]:
    log.debug("GET /api/trips")
    try:
        trips = TripRepo.list_all()
        owner_ids = list({t.owner_id for t in trips if t.owner_id})
        ratings = ReviewRepo.bulk_ratings(owner_ids)
        log.debug("list_trips: %d résultats", len(trips))
        return [_serialize(t, ratings) for t in trips]
    except Exception as e:
        log.exception("Erreur dans GET /api/trips: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(body: TripIn, user: User = Depends(require_user)) -> TripOut:
    log.debug("POST /api/trips — user_id=%s", user.id)
    try:
        trip = TripRepo.create(owner_id=user.id, **body.model_dump())
        log.debug("Trip created: id=%s", trip.id)
        return _serialize(trip)
    except Exception as e:
        log.exception("Erreur dans POST /api/trips: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, user: User = Depends(require_user)) -> None:
    log.debug("DELETE /api/trips/%s — user_id=%s", trip_id, user.id)
    if not TripRepo.delete(trip_id, user.id):
        raise HTTPException(status_code=404, detail="Trajet introuvable ou non autorisé")
