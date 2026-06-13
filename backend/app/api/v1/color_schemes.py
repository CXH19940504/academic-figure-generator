"""Color scheme CRUD endpoints — personal-use (no auth)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.base import get_schema
from app.core.exceptions import BadRequestException
from app.dependencies import get_db
from app.schemas.color_scheme import (
    ColorSchemeCreate,
    ColorSchemeResponse,
    ColorSchemeUpdate,
)

router = APIRouter(prefix="/color-schemes", tags=["Color Schemes"])


@router.get("/", response_model=list[ColorSchemeResponse])
async def list_color_schemes(
    db: AsyncSession = Depends(get_db),
):
    """List all color schemes (presets + custom)."""
    result = await db.execute(
        select(ColorScheme)
        .order_by(ColorScheme.is_default.desc(), ColorScheme.name.asc())
    )
    return [ColorSchemeResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/", response_model=ColorSchemeResponse, status_code=201)
async def create_color_scheme(
    data: ColorSchemeCreate,
    db: AsyncSession = Depends(get_db),
):
    scheme = ColorScheme(
        name=data.name,
        type="custom",
        colors=data.colors.model_dump(),
        is_default=False,
    )
    db.add(scheme)
    await db.flush()
    await db.refresh(scheme)
    return ColorSchemeResponse.model_validate(scheme)


@router.put("/{scheme_id}", response_model=ColorSchemeResponse)
async def update_color_scheme(
    scheme_id: str,
    data: ColorSchemeUpdate,
    db: AsyncSession = Depends(get_db),
):
    scheme = await get_schema(scheme_id, db)
    if scheme.type == "preset":
        raise BadRequestException("Cannot edit a system preset color scheme")

    if data.name is not None:
        scheme.name = data.name
    if data.colors is not None:
        scheme.colors = data.colors.model_dump()

    db.add(scheme)
    await db.flush()
    await db.refresh(scheme)
    return ColorSchemeResponse.model_validate(scheme)


@router.delete("/{scheme_id}", status_code=204)
async def delete_color_scheme(
    scheme_id: str,
    db: AsyncSession = Depends(get_db),
):
    scheme = await get_schema(scheme_id, db)
    if scheme.type == "preset":
        raise BadRequestException("Cannot delete a system preset color scheme")
    await db.delete(scheme)
    await db.flush()
