import logging
from fastapi import APIRouter, Depends, HTTPException, status
from godata.repos import ParcelRepo
from godata.models import Parcel, User
from ..schemas import ParcelIn, ParcelOut
from ..auth import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parcels", tags=["parcels"])


def _serialize(p: Parcel) -> ParcelOut:
    return ParcelOut(
        id=p.id,
        from_city=p.from_city,
        to_city=p.to_city,
        description=p.description,
        budget=p.budget,
        wa=p.wa,
        owner_id=p.owner_id,
        created_at=p.created_at,
    )


@router.get("", response_model=list[ParcelOut])
def list_parcels() -> list[ParcelOut]:
    log.debug("GET /api/parcels")
    try:
        parcels = ParcelRepo.list_all()
        log.debug("list_parcels: %d résultats", len(parcels))
        return [_serialize(p) for p in parcels]
    except Exception as e:
        log.exception("Erreur dans GET /api/parcels: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ParcelOut, status_code=status.HTTP_201_CREATED)
def create_parcel(body: ParcelIn, user: User = Depends(require_user)) -> ParcelOut:
    log.debug("POST /api/parcels — user_id=%s", user.id)
    try:
        parcel = ParcelRepo.create(owner_id=user.id, **body.model_dump())
        log.debug("Parcel created: id=%s", parcel.id)
        return _serialize(parcel)
    except Exception as e:
        log.exception("Erreur dans POST /api/parcels: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(parcel_id: int, user: User = Depends(require_user)) -> None:
    log.debug("DELETE /api/parcels/%s — user_id=%s", parcel_id, user.id)
    if not ParcelRepo.delete(parcel_id, user.id):
        raise HTTPException(status_code=404, detail="Colis introuvable ou non autorisé")
