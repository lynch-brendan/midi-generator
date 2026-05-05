"""
Upload all FL Studio drum packs to Cloudflare R2.
Run once manually from the project root:
    python3 scripts/upload_drums.py

Requires env vars: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
                   R2_BUCKET_NAME, R2_PUBLIC_URL
"""
import os
import sys
import json
import io
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is not installed. Run: pip install boto3")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SOURCE_DIR = Path(
    "/Applications/FL Studio 21.app/Contents/Resources/FL/Data/Patches/Packs/All drum packs"
)

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")


def _make_client():
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("ERROR: Missing one or more R2 env vars (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
              "R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME)")
        sys.exit(1)

    endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _key_exists(client, key: str) -> bool:
    """Return True if a key already exists in the bucket."""
    try:
        client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def _pack_index_key(pack_name: str) -> str:
    return f"drums/{pack_name}/.index_complete"


def upload_packs():
    if not SOURCE_DIR.exists():
        print(f"ERROR: Source directory not found:\n  {SOURCE_DIR}")
        sys.exit(1)

    client = _make_client()

    # Collect all pack directories (immediate subdirectories of SOURCE_DIR)
    pack_dirs = sorted([p for p in SOURCE_DIR.iterdir() if p.is_dir()])
    if not pack_dirs:
        print("No pack directories found under source dir.")
        sys.exit(0)

    uploaded_pack_names = []

    for pack_dir in pack_dirs:
        pack_name = pack_dir.name

        # Skip already-uploaded packs (sentinel object written at the end of upload)
        sentinel_key = _pack_index_key(pack_name)
        if _key_exists(client, sentinel_key):
            print(f"  Skipping {pack_name} (already uploaded)")
            uploaded_pack_names.append(pack_name)
            continue

        wav_files = sorted([f for f in pack_dir.iterdir()
                            if f.is_file() and f.suffix.lower() == ".wav"])
        total = len(wav_files)
        if total == 0:
            print(f"  Skipping {pack_name} (no WAV files)")
            continue

        print(f"Uploading {pack_name}...")
        for idx, wav_file in enumerate(wav_files, start=1):
            r2_key = f"drums/{pack_name}/{wav_file.name}"
            print(f"  {pack_name}... {idx}/{total} files", end="\r")
            try:
                client.upload_file(
                    str(wav_file),
                    R2_BUCKET_NAME,
                    r2_key,
                    ExtraArgs={"ContentType": "audio/wav"},
                )
            except Exception as e:
                print(f"\n  [warn] Failed to upload {wav_file.name}: {e}")

        # Write sentinel so we can skip this pack next run
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=sentinel_key,
            Body=b"done",
        )
        print(f"  {pack_name}... {total}/{total} files — done          ")
        uploaded_pack_names.append(pack_name)

    # Write the master index
    print("\nWriting drums/index.json to R2...")
    index_data = json.dumps(sorted(uploaded_pack_names), indent=2).encode()
    client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key="drums/index.json",
        Body=index_data,
        ContentType="application/json",
    )
    print(f"Done. {len(uploaded_pack_names)} packs indexed.")


if __name__ == "__main__":
    upload_packs()
