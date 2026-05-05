"""
Fetches drum kits from Cloudflare R2 and caches them locally.

Public API:
    get_kit_names()          -> list[str]
    get_kit_dir(kit_name)    -> Path | None
    auto_map_kit(kit_dir)    -> dict[int, str]
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    _boto3_available = True
except ImportError:
    _boto3_available = False

CACHE_DIR = Path("/tmp/drum_cache")

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")

_FALLBACK_KIT_NAMES = ["Roland Tr-808"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _r2_available() -> bool:
    return (
        _boto3_available
        and bool(R2_ACCOUNT_ID)
        and bool(R2_ACCESS_KEY_ID)
        and bool(R2_SECRET_ACCESS_KEY)
        and bool(R2_BUCKET_NAME)
    )


def _make_client():
    endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_kit_names() -> List[str]:
    """
    Download drums/index.json from R2 and return the list of pack names.
    Returns ["Roland Tr-808"] as a safe fallback if R2 is unavailable.
    """
    if not _r2_available():
        return list(_FALLBACK_KIT_NAMES)

    try:
        client = _make_client()
        response = client.get_object(Bucket=R2_BUCKET_NAME, Key="drums/index.json")
        names = json.loads(response["Body"].read())
        if isinstance(names, list) and names:
            return names
        return list(_FALLBACK_KIT_NAMES)
    except Exception as e:
        print(f"  [drum_kits] Could not fetch index from R2: {e}")
        return list(_FALLBACK_KIT_NAMES)


def get_kit_dir(kit_name: str) -> Optional[Path]:
    """
    Return a local Path to the cached kit directory, downloading from R2 if needed.
    Returns None if the kit cannot be obtained.
    """
    kit_cache = CACHE_DIR / kit_name

    # Already cached?
    if kit_cache.exists() and any(kit_cache.iterdir()):
        return kit_cache

    if not _r2_available():
        return None

    try:
        client = _make_client()
        prefix = f"drums/{kit_name}/"

        # List all objects under this prefix
        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix)

        wav_keys = []
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".wav"):
                    wav_keys.append(key)

        if not wav_keys:
            print(f"  [drum_kits] No WAV files found in R2 for kit: {kit_name}")
            return None

        kit_cache.mkdir(parents=True, exist_ok=True)

        for key in wav_keys:
            filename = Path(key).name
            local_path = kit_cache / filename
            if not local_path.exists():
                client.download_file(R2_BUCKET_NAME, key, str(local_path))

        return kit_cache

    except Exception as e:
        print(f"  [drum_kits] Could not download kit '{kit_name}' from R2: {e}")
        return None


def auto_map_kit(kit_dir: Path) -> Dict[int, str]:
    """
    Scan filenames in kit_dir and return a GM pitch → filename mapping using
    keyword detection. Case-insensitive. When multiple files match a slot, the
    first alphabetically is chosen.

    GM pitch assignments:
        36, 35 — kick
        38, 40 — snare
        37      — rim / side stick
        39      — clap
        42, 44  — closed hi-hat
        46      — open hi-hat
        49      — crash
        51      — ride
        50, 48  — high tom
        47, 45  — mid tom
        43, 41  — low tom / floor tom
    """
    wav_files = sorted(
        f.name for f in kit_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".wav"
    )

    def _first_match(*keywords) -> Optional[str]:
        for fname in wav_files:
            lower = fname.lower()
            if any(kw in lower for kw in keywords):
                return fname
        return None

    kick  = _first_match("kick", "bd", "bass drum", "bassdrum")
    snare = _first_match("snare", "sd", "snr")
    rim   = _first_match("rim", "rs", "rimshot", "sidestick", "side_stick", "side-stick")
    clap  = _first_match("clap", "cp", "clp")
    chh   = _first_match("closed hat", "closed_hat", "closed-hat", "hat_c", "hat-c",
                          "_ch_", "-ch-", "_ch.", "-ch.", "hh_c", "hh-c", "hihat_c",
                          "hihat-c", "hi-hat_c", "hi-hat-c",
                          # Generic closed/hat keywords (order matters — checked after specific ones)
                          "chh", "clsd", "closed")
    # Fallback: any generic hat/hh that isn't open
    if chh is None:
        for fname in wav_files:
            lower = fname.lower()
            if ("hat" in lower or "hh" in lower) and "open" not in lower and "oh" not in lower:
                chh = fname
                break

    ohh   = _first_match("open hat", "open_hat", "open-hat", "hat_o", "hat-o",
                          "ohh", "opn", "_oh_", "-oh-", "_oh.", "-oh.",
                          "hh_o", "hh-o", "hihat_o", "hihat-o",
                          "hi-hat_o", "hi-hat-o", "openhat")
    # Fallback: any hat/hh with "open" or "oh"
    if ohh is None:
        for fname in wav_files:
            lower = fname.lower()
            if ("hat" in lower or "hh" in lower) and ("open" in lower or "oh" in lower):
                ohh = fname
                break

    crash = _first_match("crash", "cy", "cymbal")
    ride  = _first_match("ride")
    htom  = _first_match("high tom", "hi tom", "hitom", "hi_tom", "hi-tom", "ht", "tom_h", "tom-h", "tom1")
    mtom  = _first_match("mid tom", "mid_tom", "mid-tom", "mt", "mc", "tom_m", "tom-m", "tom2")
    ltom  = _first_match("low tom", "lo tom", "lotom", "lo_tom", "lo-tom", "lt", "lc",
                          "floor", "tom_l", "tom-l", "tom3")

    mapping: Dict[int, str] = {}

    if kick:
        mapping[36] = kick
        mapping[35] = kick
    if snare:
        mapping[38] = snare
        mapping[40] = snare
    if rim:
        mapping[37] = rim
    if clap:
        mapping[39] = clap
    if chh:
        mapping[42] = chh
        mapping[44] = chh
    if ohh:
        mapping[46] = ohh
    if crash:
        mapping[49] = crash
    if ride:
        mapping[51] = ride
    if htom:
        mapping[50] = htom
        mapping[48] = htom
    if mtom:
        mapping[47] = mtom
        mapping[45] = mtom
    if ltom:
        mapping[43] = ltom
        mapping[41] = ltom

    return mapping
