from fastapi import APIRouter, Depends, HTTPException, status
from godata.repos import ParcelRepo
from godata.models import Parcel, User
from ..schemas import ParcelIn, ParcelOut
from ..auth import require_user

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
    return [_serialize(p) for p in ParcelRepo.list_all()]


@router.post("", response_model=ParcelOut, status_code=status.HTTP_201_CREATED)
def create_parcel(body: ParcelIn, user: User = Depends(require_user)) -> ParcelOut:
    parcel = ParcelRepo.create(owner_id=user.id, **body.model_dump())
    return _serialize(parcel)


@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(parcel_id: int, user: User = Depends(require_user)) -> None:
    if not ParcelRepo.delete(parcel_id, user.id):
        raise HTTPException(status_code=404, detail="Colis introuvable ou non autorisé")
