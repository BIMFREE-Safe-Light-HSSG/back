import os
import re
from typing import Any

import httpx


KAKAO_COORD2REGIONCODE_URL = (
    "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
)
KAKAO_COORD2ADDRESS_URL = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
DEFAULT_KAKAO_LOCAL_API_TIMEOUT_SECONDS = 5.0


class GeoConfigurationError(Exception):
    pass


class GeoProviderError(Exception):
    pass


class GeoNoResultError(Exception):
    pass


def _kakao_rest_api_key() -> str:
    key = os.getenv("KAKAO_REST_API_KEY")
    if not key or not key.strip():
        raise GeoConfigurationError("KAKAO_REST_API_KEY is not configured.")

    return key.strip()


def _kakao_timeout() -> float:
    raw_timeout = os.getenv(
        "KAKAO_LOCAL_API_TIMEOUT_SECONDS",
        str(DEFAULT_KAKAO_LOCAL_API_TIMEOUT_SECONDS),
    )

    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise GeoConfigurationError(
            "KAKAO_LOCAL_API_TIMEOUT_SECONDS must be a number."
        ) from exc

    if timeout <= 0:
        raise GeoConfigurationError(
            "KAKAO_LOCAL_API_TIMEOUT_SECONDS must be greater than 0."
        )

    return timeout


def _district_name_from_address(address: str | None) -> str | None:
    if not address:
        return None

    for suffix in ("구", "군"):
        match = re.search(rf"([가-힣A-Za-z0-9]+{suffix})", address)
        if match:
            return match.group(1)

    match = re.search(r"([가-힣A-Za-z0-9]+시)", address)
    if match:
        return match.group(1)

    tokens = address.split()
    return tokens[0] if tokens else None


def _normalize_area_code(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip()).upper()


def fallback_location_from_address(
    latitude: float,
    longitude: float,
    address: str,
) -> dict[str, Any]:
    district_name = _district_name_from_address(address)
    if not district_name:
        district_name = f"{round(latitude, 4)},{round(longitude, 4)}"

    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "building_name": None,
        "district_code": _normalize_area_code(district_name),
        "district_name": district_name,
        "region_1depth_name": None,
        "region_2depth_name": district_name,
        "region_3depth_name": None,
        "provider": "FALLBACK",
    }


def _pick_region_document(documents: list[dict[str, Any]]) -> dict[str, Any]:
    for document in documents:
        if document.get("region_type") == "H":
            return document

    for document in documents:
        if document.get("region_type") == "B":
            return document

    if documents:
        return documents[0]

    raise GeoNoResultError("No region result for the selected coordinates.")


def _pick_address_document(documents: list[dict[str, Any]]) -> dict[str, Any] | None:
    return documents[0] if documents else None


async def reverse_geocode(latitude: float, longitude: float) -> dict[str, Any]:
    headers = {"Authorization": f"KakaoAK {_kakao_rest_api_key()}"}
    params = {
        "x": str(longitude),
        "y": str(latitude),
        "input_coord": "WGS84",
    }

    try:
        async with httpx.AsyncClient(timeout=_kakao_timeout()) as client:
            region_response = await client.get(
                KAKAO_COORD2REGIONCODE_URL,
                headers=headers,
                params=params,
            )
            region_response.raise_for_status()

            address_response = await client.get(
                KAKAO_COORD2ADDRESS_URL,
                headers=headers,
                params=params,
            )
            address_response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise GeoProviderError(
            f"Kakao Local API returned {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GeoProviderError(f"Failed to request Kakao Local API: {exc}") from exc

    try:
        region_json = region_response.json()
        address_json = address_response.json()
    except ValueError as exc:
        raise GeoProviderError("Kakao Local API response must be valid JSON.") from exc

    region_document = _pick_region_document(region_json.get("documents", []))
    address_document = _pick_address_document(address_json.get("documents", []))

    road_address = address_document.get("road_address") if address_document else None
    jibun_address = address_document.get("address") if address_document else None
    address = None
    building_name = None
    if isinstance(road_address, dict):
        address = road_address.get("address_name") or None
        building_name = road_address.get("building_name") or None
    if address is None and isinstance(jibun_address, dict):
        address = jibun_address.get("address_name") or None

    district_name = region_document.get("region_2depth_name")
    region_code = region_document.get("code")
    if not district_name or not region_code:
        raise GeoNoResultError("Kakao Local API returned incomplete region data.")
    district_code = region_code[:5] if len(region_code) >= 5 else region_code

    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "building_name": building_name,
        "district_code": district_code,
        "district_name": district_name,
        "region_1depth_name": region_document.get("region_1depth_name") or None,
        "region_2depth_name": district_name,
        "region_3depth_name": region_document.get("region_3depth_name") or None,
        "provider": "KAKAO",
    }
