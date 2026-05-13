from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.geo import ReverseGeocodeResponse
from app.services.geo_service import (
    GeoConfigurationError,
    GeoNoResultError,
    GeoProviderError,
    reverse_geocode,
)


router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/reverse-geocode", response_model=ReverseGeocodeResponse)
async def read_reverse_geocode(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> ReverseGeocodeResponse:
    try:
        location = await reverse_geocode(latitude, longitude)
    except GeoConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except GeoProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except GeoNoResultError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ReverseGeocodeResponse(**location)
