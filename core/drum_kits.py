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
LOCAL_KITS_DIR = Path(__file__).parent.parent / "samples" / "drums"

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

def _local_kit_names() -> List[str]:
    """Kit subdirectories present in samples/drums/."""
    if not LOCAL_KITS_DIR.exists():
        return []
    return [d.name for d in LOCAL_KITS_DIR.iterdir()
            if d.is_dir() and any(f.suffix.lower() == ".wav" for f in d.iterdir())]


def get_kit_names() -> List[str]:
    """
    Return available kit names — local samples/drums/ subfolders first, then R2.
    """
    local = _local_kit_names()
    if local:
        return local
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


def _resolve_kit_name(requested: str, known: List[str]) -> str:
    """
    Find the best match for `requested` among `known` kit names.
    Priority: exact → case-insensitive exact → best substring overlap.
    """
    if requested in known:
        return requested
    lower = requested.lower()
    # Case-insensitive exact match
    for k in known:
        if k.lower() == lower:
            return k
    # Substring: requested is contained in a known name
    for k in known:
        if lower in k.lower():
            return k
    # Substring: known name is contained in requested
    for k in known:
        if k.lower() in lower:
            return k
    return requested  # no match found — will likely 404, that's OK


def get_kit_dir(kit_name: str) -> Optional[Path]:
    """
    Return a local Path to the kit directory.
    Checks samples/drums/<kit_name>/ first, then R2.
    Does case-insensitive / fuzzy matching.
    Returns None if the kit cannot be obtained.
    """
    # Check local samples first
    local_names = _local_kit_names()
    if local_names:
        resolved = _resolve_kit_name(kit_name, local_names)
        local_kit = LOCAL_KITS_DIR / resolved
        if local_kit.exists() and any(f.suffix.lower() == ".wav" for f in local_kit.iterdir()):
            return local_kit

    if not _r2_available():
        return None

    # Resolve to the canonical name used in R2
    canonical = _resolve_kit_name(kit_name, get_kit_names())
    kit_cache = CACHE_DIR / canonical

    # Already cached?
    if kit_cache.exists() and any(kit_cache.iterdir()):
        return kit_cache

    try:
        client = _make_client()
        prefix = f"drums/{canonical}/"

        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix)

        wav_keys = []
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".wav"):
                    wav_keys.append(key)

        if not wav_keys:
            print(f"  [drum_kits] No WAV files found in R2 for kit: {canonical}")
            return None

        kit_cache.mkdir(parents=True, exist_ok=True)

        for key in wav_keys:
            filename = Path(key).name
            local_path = kit_cache / filename
            if not local_path.exists():
                client.download_file(R2_BUCKET_NAME, key, str(local_path))

        return kit_cache

    except Exception as e:
        print(f"  [drum_kits] Could not download kit '{canonical}' from R2: {e}")
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

    kick  = _first_match("kick", "bd", "bass drum", "bassdrum", "bsdrum", "kick1", "kick_1")
    snare = _first_match("snare", "sd", "snr", "sn1", "sn_1", "_sn.", "_sn_", "-sn-", "-sn.")
    rim   = _first_match("rim", "rs", "rimshot", "sidestick", "side_stick", "side-stick")
    clap  = _first_match("clap", "cp", "clp")
    chh   = _first_match("closed hat", "closed_hat", "closed-hat", "hat_c", "hat-c",
                          "_ch_", "-ch-", "_ch.", "-ch.", "hh_c", "hh-c", "hihat_c",
                          "hihat-c", "hi-hat_c", "hi-hat-c",
                          "chh", "clsd", "closed", "hat_closed", "hat-closed")
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
