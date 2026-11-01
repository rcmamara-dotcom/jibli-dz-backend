import logging
from fastapi import APIRouter, Depends, HTTPException, status
from godata.models import User, Trip, Parcel, Review
from godata.repos import UserRepo, TripRepo, ParcelRepo, ReviewRepo
from ..schemas import UserAdminOut, AdminStatsOut, TripOut, ParcelOut, ReviewOut
from ..auth import require_admin

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsOut)
def stats(_: User = Depends(require_admin)) -> AdminStatsOut:
    return AdminStatsOut(
        users=User.select().count(),
        trips=Trip.select().count(),
        parcels=Parcel.select().count(),
        reviews=Review.select().count(),
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserAdminOut])
def list_users(_: User = Depends(require_admin)) -> list[UserAdminOut]:
    return [UserAdminOut.model_validate(u) for u in UserRepo.list_all()]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, me: User = Depends(require_admin)) -> None:
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")
    if not UserRepo.force_delete(user_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")


# ── Trips ─────────────────────────────────────────────────────────────────────

def _trip_out(t: Trip) -> TripOut:
    return TripOut(
        id=t.id, name=t.name, from_city=t.from_city, to_city=t.to_city,
        date=t.date, capacity=t.capacity, weight=t.weight, cap_desc=t.cap_desc,
        wa=t.wa, owner_id=t.owner_id, created_at=t.created_at,
    )


@router.get("/trips", response_model=list[TripOut])
def list_trips(_: User = Depends(require_admin)) -> list[TripOut]:
    return [_trip_out(t) for t in TripRepo.list_all()]


@router.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, _: User = Depends(require_admin)) -> None:
    if not TripRepo.force_delete(trip_id):
        raise HTTPException(status_code=404, detail="Trajet introuvable")


# ── Parcels ───────────────────────────────────────────────────────────────────

def _parcel_out(p: Parcel) -> ParcelOut:
    return ParcelOut(
        id=p.id, from_city=p.from_city, to_city=p.to_city,
        description=p.description, budget=p.budget,
        wa=p.wa, owner_id=p.owner_id, created_at=p.created_at,
    )


@router.get("/parcels", response_model=list[ParcelOut])
def list_parcels(_: User = Depends(require_admin)) -> list[ParcelOut]:
    return [_parcel_out(p) for p in ParcelRepo.list_all()]


@router.delete("/parcels/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(parcel_id: int, _: User = Depends(require_admin)) -> None:
    if not ParcelRepo.force_delete(parcel_id):
        raise HTTPException(status_code=404, detail="Colis introuvable")


# ── Reviews ───────────────────────────────────────────────────────────────────

def _review_out(r: Review) -> ReviewOut:
    return ReviewOut(
        id=r.id, trip_id=r.trip_id, reviewer_id=r.reviewer_id,
        reviewer_email=r.reviewer.email, rating=r.rating,
        comment=r.comment, created_at=r.created_at,
    )


@router.get("/reviews", response_model=list[ReviewOut])
def list_reviews(_: User = Depends(require_admin)) -> list[ReviewOut]:
    return [_review_out(r) for r in ReviewRepo.list_all()]


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: int, _: User = Depends(require_admin)) -> None:
    if not ReviewRepo.force_delete(review_id):
        raise HTTPException(status_code=404, detail="Avis introuvable")
