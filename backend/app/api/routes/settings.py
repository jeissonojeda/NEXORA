from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.currencies import SUPPORTED_CURRENCIES
from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.settings import SettingsCurrencyOut, SettingsResponse, SettingsUpdate
from app.services.logo_service import MAX_LOGO_BYTES, LogoService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Configuración"])


@router.get("", response_model=SettingsResponse)
def get_settings(
    _: Annotated[User, Depends(require_permission("settings.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> SettingsResponse:
    return SettingsResponse.model_validate(SettingsService(db).get_settings())


@router.get("/currencies", response_model=list[SettingsCurrencyOut])
def list_currencies(
    _: Annotated[User, Depends(require_permission("settings.read"))],
) -> list[SettingsCurrencyOut]:
    return [
        SettingsCurrencyOut(
            code=code,
            name=info["name"],
            symbol=info["symbol"],
            locale=info["locale"],
            decimals=info["decimals"],
        )
        for code, info in SUPPORTED_CURRENCIES.items()
    ]


@router.put("", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdate,
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> SettingsResponse:
    fields = payload.model_dump(exclude_unset=True)
    confirm = bool(fields.pop("confirm_currency_change", False))
    settings = SettingsService(db).update_settings(fields, confirm_currency_change=confirm)
    return SettingsResponse.model_validate(settings)


@router.post("/reset", response_model=SettingsResponse)
def reset_settings(
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
    payload: Annotated[SettingsUpdate | None, Body()] = None,
) -> SettingsResponse:
    confirm = bool(payload.confirm_currency_change) if payload else False
    settings = SettingsService(db).reset_defaults(confirm_currency_change=confirm)
    return SettingsResponse.model_validate(settings)


@router.get("/logo")
def get_logo(
    _: Annotated[User, Depends(require_permission("settings.read"))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    content, mime = LogoService(db).get_logo_file()
    return Response(content=content, media_type=mime)


@router.post("/logo", response_model=SettingsResponse)
async def upload_logo(
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> SettingsResponse:
    content = await file.read(MAX_LOGO_BYTES + 1)
    settings = LogoService(db).set_logo(content, file.filename)
    return SettingsResponse.model_validate(settings)


@router.delete("/logo", response_model=SettingsResponse)
def delete_logo(
    _: Annotated[User, Depends(require_permission("settings.update"))],
    db: Annotated[Session, Depends(get_db)],
) -> SettingsResponse:
    settings = LogoService(db).delete_logo()
    return SettingsResponse.model_validate(settings)
