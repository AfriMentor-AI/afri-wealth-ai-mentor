"""Insights router — /api/v1/insights (card O3.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import InsightFavorite, InsightItem
from ..schemas import InsightItemCreate, InsightItemResponse

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


def _get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    return x_user_id


def _require_admin(x_user_roles: str = Header("", alias="X-User-Roles")) -> None:
    """Catalog authoring is admin-only — gateway forwards verified JWT roles as
    X-User-Roles, so this trusts the header the same way _get_user trusts X-User-Id."""
    roles = {r.strip() for r in x_user_roles.split(",") if r.strip()}
    if "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def _favorited_ids(db: Session, user_id: str) -> set[str]:
    rows = db.scalars(
        select(InsightFavorite.insight_id).where(InsightFavorite.user_id == user_id)
    ).all()
    return set(rows)


def _to_response(item: InsightItem, favorited: set[str]) -> InsightItemResponse:
    resp = InsightItemResponse.model_validate(item)
    resp.is_favorited = item.id in favorited
    return resp


@router.get("", response_model=list[InsightItemResponse])
def list_insights(
    search: str | None = None,
    category: str | None = None,
    is_audio: bool | None = None,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[InsightItemResponse]:
    query = db.query(InsightItem)
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(
            InsightItem.title.ilike(like) | InsightItem.summary.ilike(like)
        )
    if category:
        query = query.filter(InsightItem.category == category)
    if is_audio is not None:
        query = query.filter(InsightItem.is_audio == is_audio)

    items = query.order_by(InsightItem.created_at.desc()).all()
    favorited = _favorited_ids(db, user_id)
    return [_to_response(i, favorited) for i in items]


@router.get("/bookmarks", response_model=list[InsightItemResponse])
def list_bookmarks(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[InsightItemResponse]:
    favorited = _favorited_ids(db, user_id)
    if not favorited:
        return []
    items = db.query(InsightItem).filter(InsightItem.id.in_(favorited)).all()
    return [_to_response(i, favorited) for i in items]


@router.get("/{insight_id}", response_model=InsightItemResponse)
def get_insight(
    insight_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> InsightItemResponse:
    item = db.get(InsightItem, insight_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    return _to_response(item, _favorited_ids(db, user_id))


@router.post("", response_model=InsightItemResponse, status_code=status.HTTP_201_CREATED)
def create_insight(
    body: InsightItemCreate,
    _admin: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> InsightItemResponse:
    item = InsightItem(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_response(item, set())


@router.post(
    "/{insight_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
def bookmark_insight(
    insight_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Response:
    item = db.get(InsightItem, insight_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    existing = db.get(InsightFavorite, (user_id, insight_id))
    if not existing:
        db.add(InsightFavorite(user_id=user_id, insight_id=insight_id))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{insight_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
def unbookmark_insight(
    insight_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Response:
    existing = db.get(InsightFavorite, (user_id, insight_id))
    if existing:
        db.delete(existing)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
