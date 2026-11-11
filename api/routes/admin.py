import logging
from fastapi import APIRouter, Depends, HTTPException, status
from godata.models import ROLES, User, Trip, Parcel, UserReview
from godata.repos import UserRepo, TripRepo, ParcelRepo, UserReviewRepo
from ..schemas import UserAdminOut, AdminStatsOut, RoleIn, TripOut, ParcelOut, AdminReviewOut
from .reviews import public_name
from ..permissions import require

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsOut)
def stats(_: User = Depends(require("moderate"))) -> AdminStatsOut:
    return AdminStatsOut(
        users=User.select().count(),
        trips=Trip.select().count(),
        parcels=Parcel.select().count(),
        reviews=UserReview.select().count(),
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserAdminOut])
def list_users(_: User = Depends(require("manage_users"))) -> list[UserAdminOut]:
    return [UserAdminOut.model_validate(u) for u in UserRepo.list_all()]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, me: User = Depends(require("manage_users"))) -> None:
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")
    if not UserRepo.force_delete(user_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")


@router.patch("/users/{user_id}/role", response_model=UserAdminOut)
def set_role(user_id: int, body: RoleIn, me: User = Depends(require("manage_users"))) -> UserAdminOut:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail="Rôle inconnu")
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="Tu ne peux pas changer ton propre rôle")
    if not UserRepo.set_role(user_id, body.role):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    log.info("Rôle de user_id=%s → %s (par admin %s)", user_id, body.role, me.id)
    return UserAdminOut.model_validate(UserRepo.get_by_id(user_id))


# ── Trips ─────────────────────────────────────────────────────────────────────

def _trip_out(t: Trip) -> TripOut:
    return TripOut(
        id=t.id, name=t.name, from_city=t.from_city, to_city=t.to_city,
        date=t.date, capacity=t.capacity, weight=t.weight, cap_desc=t.cap_desc,
        wa=t.wa, owner_id=t.owner_id, created_at=t.created_at,
    )


@router.get("/trips", response_model=list[TripOut])
def list_trips(_: User = Depends(require("moderate"))) -> list[TripOut]:
    return [_trip_out(t) for t in TripRepo.list_all()]


@router.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, _: User = Depends(require("moderate"))) -> None:
    if not TripRepo.force_delete(trip_id):
        raise HTTPException(status_code=404, detail="Trajet introuvable")


# ── Parcels ───────────────────────────────────────────────────────────────────

def _parcel_out(p: Parcel) -> ParcelOut:
    return ParcelOut.model_validate(p)


@router.get("/parcels", response_model=list[ParcelOut])
def list_parcels(_: User = Depends(require("moderate"))) -> list[ParcelOut]:
    return [_parcel_out(p) for p in ParcelRepo.list_all()]


@router.delete("/parcels/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(parcel_id: int, _: User = Depends(require("moderate"))) -> None:
    if not ParcelRepo.force_delete(parcel_id):
        raise HTTPException(status_code=404, detail="Colis introuvable")


# ── Reviews ───────────────────────────────────────────────────────────────────

def _review_out(r: UserReview) -> AdminReviewOut:
    return AdminReviewOut(
        id=r.id, reviewer_name=public_name(r.reviewer), reviewed_id=r.reviewed_id,
        reviewed_name=public_name(r.reviewed), rating=r.rating,
        comment=r.comment, created_at=r.created_at,
    )


@router.get("/reviews", response_model=list[AdminReviewOut])
def list_reviews(_: User = Depends(require("moderate"))) -> list[AdminReviewOut]:
    return [_review_out(r) for r in UserReviewRepo.list_all()]


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: int, _: User = Depends(require("moderate"))) -> None:
    if not UserReviewRepo.force_delete(review_id):
        raise HTTPException(status_code=404, detail="Avis introuvable")
