import datetime as dt
import hashlib
import hmac
import os
from urllib.parse import quote, urlsplit


AWS_ALGORITHM = "AWS4-HMAC-SHA256"
AWS_SERVICE = "s3"
DEFAULT_REGION = "us-east-1"
MAX_PRESIGNED_URL_EXPIRES_SECONDS = 604_800


class StorageConfigurationError(Exception):
    pass


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise StorageConfigurationError(f"{name} is not configured.")

    value = value.strip()
    if not value:
        if default is not None:
            return default
        raise StorageConfigurationError(f"{name} is not configured.")

    return value


def bucket_name() -> str:
    return _env("MINIO_BUCKET_NAME", "scan-files")


def public_endpoint() -> str:
    endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT")
    if endpoint and endpoint.strip():
        return endpoint.strip().rstrip("/")

    public_domain = _env("MINIO_PUBLIC_DOMAIN", "supersafetwin-minio.duckdns.org").rstrip("/")
    if public_domain.startswith(("http://", "https://")):
        return public_domain.rstrip("/")

    scheme = _env("MINIO_PUBLIC_SCHEME", "https")
    return f"{scheme}://{public_domain}"


def presigned_url_expires_in() -> int:
    raw_expires = _env("MINIO_PRESIGNED_URL_EXPIRES_SECONDS", "900")
    try:
        expires = int(raw_expires)
    except ValueError as exc:
        raise StorageConfigurationError(
            "MINIO_PRESIGNED_URL_EXPIRES_SECONDS must be an integer."
        ) from exc

    if expires < 1 or expires > MAX_PRESIGNED_URL_EXPIRES_SECONDS:
        raise StorageConfigurationError(
            "MINIO_PRESIGNED_URL_EXPIRES_SECONDS must be between 1 and 604800."
        )

    return expires


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    date_key = _sign(f"AWS4{secret_key}".encode("utf-8"), date_stamp)
    region_key = _sign(date_key, region)
    service_key = _sign(region_key, AWS_SERVICE)
    return _sign(service_key, "aws4_request")


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(
        f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}"
        for key, value in sorted(params.items())
    )


def generate_presigned_put_url(
    bucket_name: str,
    object_key: str,
    expires_in: int,
) -> str:
    access_key = _env("MINIO_ROOT_USER", "minioadmin")
    secret_key = _env("MINIO_ROOT_PASSWORD", "minioadmin123")
    region = DEFAULT_REGION
    endpoint = public_endpoint()
    parsed_endpoint = urlsplit(endpoint)

    if not parsed_endpoint.scheme or not parsed_endpoint.netloc:
        raise StorageConfigurationError(
            "MinIO public endpoint must include scheme and host."
        )

    now = dt.datetime.now(dt.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    credential_scope = f"{date_stamp}/{region}/{AWS_SERVICE}/aws4_request"
    signed_headers = "host"

    path_prefix = parsed_endpoint.path.rstrip("/")
    canonical_uri = (
        f"{path_prefix}/{quote(bucket_name, safe='')}/{quote(object_key, safe='/-_.~')}"
    )
    credential = f"{access_key}/{credential_scope}"
    query_params = {
        "X-Amz-Algorithm": AWS_ALGORITHM,
        "X-Amz-Credential": credential,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in),
        "X-Amz-SignedHeaders": signed_headers,
    }
    canonical_query = _canonical_query(query_params)
    canonical_headers = f"host:{parsed_endpoint.netloc}\n"
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            "UNSIGNED-PAYLOAD",
        ]
    )
    hashed_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join(
        [
            AWS_ALGORITHM,
            amz_date,
            credential_scope,
            hashed_request,
        ]
    )
    signature = hmac.new(
        _signing_key(secret_key, date_stamp, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    final_query = f"{canonical_query}&X-Amz-Signature={signature}"
    return (
        f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        f"{canonical_uri}?{final_query}"
    )
