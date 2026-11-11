import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from godata.repos import UserRepo, UserReviewRepo
from godata.models import User, UserReview
from ..schemas import ProfileOut, ReviewIn, ReviewOut
from ..auth import get_current_user, require_user
from ..limiter import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["reviews"])


def public_name(user: User | None) -> str:
    """« Karim Meziane » → « Karim M. » ; jamais l'e-mail."""
    parts = (user.name or "").split() if user else []
    if not parts:
        return "Utilisateur"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0].upper()}."


def _serialize(r: UserReview) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        reviewer_id=r.reviewer_id,
        reviewer_name=public_name(r.reviewer),
        rating=r.rating,
        comment=r.comment,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _profile(target: User, viewer: User | None) -> ProfileOut:
    summary = UserReviewRepo.summary(target.id)
    mine = UserReviewRepo.get(viewer.id, target.id) if viewer else None
    return ProfileOut(
        id=target.id,
        name=public_name(target),
        member_since=target.created_at,
        avg=summary["avg"],
        count=summary["count"],
        distribution=summary["distribution"],
        reviews=[_serialize(r) for r in UserReviewRepo.list_for(target.id)],
        my_review=_serialize(mine) if mine else None,
        can_review=bool(viewer) and UserReviewRepo.can_review(viewer.id, target.id),
    )


@router.get("/{user_id}/profile", response_model=ProfileOut)
def get_profile(user_id: int, viewer: User | None = Depends(get_current_user)) -> ProfileOut:
    target = UserRepo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return _profile(target, viewer)


@router.put("/{user_id}/review", response_model=ProfileOut)
@limiter.limit("20/hour")
def rate_user(request: Request, user_id: int, body: ReviewIn, user: User = Depends(require_user)) -> ProfileOut:
    target = UserRepo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous noter vous-même")
    # Comme Uber : on note quelqu'un avec qui on a vraiment échangé
    if not UserReviewRepo.can_review(user.id, target.id):
        raise HTTPException(status_code=403, detail="Échangez d'abord des messages avec cette personne pour la noter")
    UserReviewRepo.upsert(user.id, target.id, body.rating, (body.comment or "").strip() or None)
    log.info("Avis user_id=%s → user_id=%s : %s★", user.id, target.id, body.rating)
    return _profile(target, user)


@router.delete("/{user_id}/review", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_review(user_id: int, user: User = Depends(require_user)) -> None:
    mine = UserReviewRepo.get(user.id, user_id)
    if not mine or not UserReviewRepo.force_delete(mine.id):
        raise HTTPException(status_code=404, detail="Avis introuvable")
