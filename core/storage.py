import os
from pathlib import Path
from typing import Optional


def r2_enabled() -> bool:
    """Return True only when all required R2 environment variables are set."""
    required = [
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
        "R2_PUBLIC_URL",
    ]
    return all(os.environ.get(v) for v in required)


def upload_to_r2(local_path: str | Path, key: str) -> Optional[str]:
    """Upload a local file to Cloudflare R2 and return its public URL.

    Returns None if the upload fails or R2 is not configured.
    """
    if not r2_enabled():
        return None

    try:
        import boto3
        from botocore.config import Config

        account_id = os.environ["R2_ACCOUNT_ID"]
        access_key = os.environ["R2_ACCESS_KEY_ID"]
        secret_key = os.environ["R2_SECRET_ACCESS_KEY"]
        bucket = os.environ["R2_BUCKET_NAME"]
        public_url = os.environ["R2_PUBLIC_URL"].rstrip("/")

        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

        local_path = Path(local_path)
        if not local_path.exists():
            return None

        # Determine a reasonable content type
        suffix = local_path.suffix.lower()
        content_type_map = {
            ".mid": "audio/midi",
            ".midi": "audio/midi",
            ".wav": "audio/wav",
        }
        content_type = content_type_map.get(suffix, "application/octet-stream")

        s3.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "ContentDisposition": f"attachment; filename=\"{local_path.name}\"",
            },
        )

        return f"{public_url}/{key}"

    except Exception:
        return None
