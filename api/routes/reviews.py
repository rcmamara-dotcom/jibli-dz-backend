import logging
from fastapi import APIRouter, Depends, HTTPException, status
from godata.repos import TripRepo, ReviewRepo
from godata.models import User, Review
from ..schemas import ReviewIn, ReviewOut
from ..auth import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trips", tags=["reviews"])


def _serialize(r: Review) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        trip_id=r.trip_id,
        reviewer_id=r.reviewer_id,
        reviewer_email=r.reviewer.email,
        rating=r.rating,
        comment=r.comment,
        created_at=r.created_at,
    )


@router.get("/{trip_id}/reviews", response_model=list[ReviewOut])
def list_reviews(trip_id: int) -> list[ReviewOut]:
    log.debug("GET /api/trips/%s/reviews", trip_id)
    return [_serialize(r) for r in ReviewRepo.list_for_trip(trip_id)]


@router.post("/{trip_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def add_review(trip_id: int, body: ReviewIn, user: User = Depends(require_user)) -> ReviewOut:
    log.debug("POST /api/trips/%s/reviews — user_id=%s rating=%s", trip_id, user.id, body.rating)

    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=422, detail="La note doit être entre 1 et 5")

    trip = TripRepo.get_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")

    if trip.owner_id == user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas noter votre propre trajet")

    if ReviewRepo.exists(trip_id, user.id):
        raise HTTPException(status_code=409, detail="Vous avez déjà laissé un avis pour ce trajet")

    review = ReviewRepo.create(trip_id, user.id, body.rating, body.comment)
    # Re-fetch avec le reviewer pour la sérialisation
    review.reviewer = user
    return _serialize(review)
