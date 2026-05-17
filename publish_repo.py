#!/usr/bin/env python3
"""publish_repo.py -- Publish a .deb package to an S3-compatible APT repository.

Generates a fully compliant Debian repository layout so clients can use:
    apt update && apt install audio-tools

GPG Key Setup (one-time):
    1. Generate:  gpg --full-generate-key    (RSA 4096, no passphrase for CI)
    2. Export public:  gpg --armor --export <KEY_ID> > audio-tools-repo.gpg.pub
    3. Export private: gpg --armor --export-secret-keys <KEY_ID> > audio-tools-repo.gpg.key
    4. Set env:   export GPG_KEY_ID=<KEY_ID>
                  export GPG_KEY_FILE=/path/to/audio-tools-repo.gpg.key
                  export GPG_PUBKEY_FILE=/path/to/audio-tools-repo.gpg.pub

Usage:
    uv run --group publish python publish_repo.py <path-to-deb> <s3-bucket>

Environment Variables:
    S3_ENDPOINT             S3-compatible endpoint
    S3_REGION               S3 region
    S3_ACCESS_KEY_ID        S3 access key
    S3_SECRET_ACCESS_KEY    S3 secret key
    S3_PREFIX               Key prefix inside the bucket (default: audio-tools)
    GPG_KEY_ID              GPG key fingerprint for signing (required)
    GPG_KEY_FILE            Path to armored private key file
    GPG_PUBKEY_FILE         Path to armored public key file
    APT_DISTS               Comma-separated distribution codenames (default: jammy,noble)
    APT_COMPONENT           Repository component (default: main)
    APT_ORIGIN              Origin field in Release (default: audio-tools)
    APT_LABEL               Label field in Release (default: audio-tools)
"""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import boto3
import gnupg
from botocore.exceptions import ClientError
from debian.deb822 import Deb822
from debian.debfile import DebFile
from dotenv import load_dotenv

_user_env = Path.home() / ".config" / "audio-tools" / ".env"
_local_env = Path(".env")
load_dotenv(_local_env if _local_env.is_file() else _user_env)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_S3_ENDPOINT = "https://<your-s3-endpoint>"
DEFAULT_S3_REGION = "us-east-1"
DEFAULT_S3_PREFIX = "audio-tools"
DEFAULT_APT_DISTS = "jammy,noble"
DEFAULT_APT_COMPONENT = "main"
DEFAULT_APT_ORIGIN = "audio-tools"
DEFAULT_APT_LABEL = "audio-tools"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def load_config() -> dict[str, str]:
    gpg_key_id = os.environ.get("GPG_KEY_ID")
    if not gpg_key_id:
        print("Error: GPG_KEY_ID environment variable is required.", file=sys.stderr)
        print("  Generate a key:  gpg --full-generate-key", file=sys.stderr)
        print("  Then export:     export GPG_KEY_ID=<KEY_ID>", file=sys.stderr)
        sys.exit(1)

    s3_access_key = os.environ.get("S3_ACCESS_KEY_ID")
    s3_secret_key = os.environ.get("S3_SECRET_ACCESS_KEY")
    if not s3_access_key or not s3_secret_key:
        print("Error: S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required.", file=sys.stderr)
        sys.exit(1)

    return {
        "s3_endpoint": os.environ.get("S3_ENDPOINT", DEFAULT_S3_ENDPOINT),
        "s3_region": os.environ.get("S3_REGION", DEFAULT_S3_REGION),
        "s3_access_key": s3_access_key,
        "s3_secret_key": s3_secret_key,
        "s3_prefix": os.environ.get("S3_PREFIX", DEFAULT_S3_PREFIX),
        "gpg_key_id": gpg_key_id,
        "gpg_key_file": os.environ.get("GPG_KEY_FILE"),
        "gpg_pubkey_file": os.environ.get("GPG_PUBKEY_FILE"),
        "dists": [d.strip() for d in os.environ.get("APT_DISTS", DEFAULT_APT_DISTS).split(",")],
        "component": os.environ.get("APT_COMPONENT", DEFAULT_APT_COMPONENT),
        "origin": os.environ.get("APT_ORIGIN", DEFAULT_APT_ORIGIN),
        "label": os.environ.get("APT_LABEL", DEFAULT_APT_LABEL),
    }


# ---------------------------------------------------------------------------
# S3 Client
# ---------------------------------------------------------------------------
def create_s3_client(config: dict[str, str]):
    return boto3.client(
        "s3",
        endpoint_url=config["s3_endpoint"],
        aws_access_key_id=config["s3_access_key"],
        aws_secret_access_key=config["s3_secret_key"],
    )


def prefixed_key(prefix: str, key: str) -> str:
    return f"{prefix}/{key}" if prefix else key


def upload_bytes(s3_client, bucket: str, key: str, data: bytes, content_type: str) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        ACL="public-read",
    )
    print(f"  Uploaded: {key} ({len(data)} bytes)")


def upload_text(s3_client, bucket: str, key: str, text: str, content_type: str = "text/plain") -> None:
    upload_bytes(s3_client, bucket, key, text.encode("utf-8"), content_type)


# ---------------------------------------------------------------------------
# .deb Metadata Extraction
# ---------------------------------------------------------------------------
def extract_deb_metadata(deb_path: str) -> dict[str, str]:
    deb = DebFile(deb_path)
    control = deb.debcontrol()
    deb_bytes = Path(deb_path).read_bytes()
    metadata = {}
    for field in ("Package", "Version", "Architecture", "Maintainer", "Installed-Size", "Depends", "Section", "Priority", "Description"):
        if field in control:
            metadata[field] = control[field]
    metadata["Size"] = str(len(deb_bytes))
    metadata["MD5sum"] = hashlib.md5(deb_bytes).hexdigest()
    metadata["SHA1"] = hashlib.sha1(deb_bytes).hexdigest()
    metadata["SHA256"] = hashlib.sha256(deb_bytes).hexdigest()
    return metadata


def compute_pool_path(metadata: dict[str, str], component: str, deb_filename: str) -> str:
    package = metadata["Package"]
    return f"pool/{component}/{package[0].lower()}/{package}/{deb_filename}"


# ---------------------------------------------------------------------------
# Packages Index Management
# ---------------------------------------------------------------------------
PACKAGES_FIELD_ORDER = [
    "Package", "Version", "Architecture", "Maintainer", "Installed-Size",
    "Depends", "Section", "Priority", "Filename", "Size", "MD5sum", "SHA1", "SHA256", "Description",
]


def build_packages_entry(metadata: dict[str, str]) -> str:
    lines = []
    for field in PACKAGES_FIELD_ORDER:
        value = metadata.get(field, "")
        if value:
            lines.append(f"{field}: {value}")
    return "\n".join(lines) + "\n"


def download_existing_packages(s3_client, bucket: str, packages_gz_key: str) -> str:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=packages_gz_key)
        return gzip.decompress(response["Body"].read()).decode("utf-8")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code", "") in ("NoSuchKey", "404"):
            return ""
        raise


def version_exists_in_repo(s3_client, bucket: str, prefix: str, config: dict[str, str], package: str, version: str, arch: str) -> bool:
    component = config["component"]
    for dist in config["dists"]:
        packages_gz_key = prefixed_key(prefix, f"dists/{dist}/{component}/binary-{arch}/Packages.gz")
        existing = download_existing_packages(s3_client, bucket, packages_gz_key)
        if not existing.strip():
            continue
        for block in existing.strip().split("\n\n"):
            if not block.strip():
                continue
            parsed = Deb822(block)
            if parsed.get("Package") == package and parsed.get("Version") == version:
                return True
    return False


def update_packages_content(existing: str, new_entry: str, package: str, version: str) -> str:
    if not existing.strip():
        return new_entry
    stanzas = []
    replaced = False
    for block in existing.strip().split("\n\n"):
        if not block.strip():
            continue
        parsed = Deb822(block)
        if parsed.get("Package") == package and parsed.get("Version") == version:
            stanzas.append(new_entry.strip())
            replaced = True
        else:
            stanzas.append(block.strip())
    if not replaced:
        stanzas.append(new_entry.strip())
    return "\n\n".join(stanzas) + "\n"


def compress_packages(packages_text: str) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(packages_text.encode("utf-8"))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Release File
# ---------------------------------------------------------------------------
def build_release(packages_text: str, packages_gz_bytes: bytes, config: dict[str, str], arch: str) -> str:
    component = config["component"]
    dist = config["dist"]
    packages_bytes = packages_text.encode("utf-8")
    files = [
        (f"{component}/binary-{arch}/Packages", packages_bytes),
        (f"{component}/binary-{arch}/Packages.gz", packages_gz_bytes),
    ]
    md5_lines = []
    sha256_lines = []
    for rel_path, data in files:
        size = len(data)
        md5_lines.append(f" {hashlib.md5(data).hexdigest()} {size:>16} {rel_path}")
        sha256_lines.append(f" {hashlib.sha256(data).hexdigest()} {size:>16} {rel_path}")
    now = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
    return (
        f"Origin: {config['origin']}\n"
        f"Label: {config['label']}\n"
        f"Suite: {dist}\n"
        f"Codename: {dist}\n"
        f"Architectures: {arch}\n"
        f"Components: {component}\n"
        f"Date: {now}\n"
        f"MD5Sum:\n" + "\n".join(md5_lines) + "\n"
        "SHA256:\n" + "\n".join(sha256_lines) + "\n"
    )


# ---------------------------------------------------------------------------
# GPG Signing
# ---------------------------------------------------------------------------
def _make_gpg_client(key_file: str | None = None) -> gnupg.GPG:
    if not key_file:
        return gnupg.GPG()
    key_path = Path(key_file)
    if not key_path.is_file():
        print(f"Error: GPG_KEY_FILE not found: {key_file}", file=sys.stderr)
        sys.exit(1)
    tmpdir = tempfile.mkdtemp(prefix="audio_tools_gpg_")
    os.chmod(tmpdir, 0o700)
    gpg_client = gnupg.GPG(gnupghome=tmpdir)
    result = gpg_client.import_keys(key_path.read_text())
    if result.count == 0:
        print(f"Error: No keys imported from {key_file}.", file=sys.stderr)
        sys.exit(1)
    return gpg_client


def sign_release(release_text: str, gpg_key_id: str, key_file: str | None = None) -> tuple[str, str]:
    gpg_client = _make_gpg_client(key_file)
    private_keys = gpg_client.list_keys(True)
    key_ids = [k["keyid"] for k in private_keys] + [k["fingerprint"] for k in private_keys]
    if not any(gpg_key_id in kid for kid in key_ids):
        print(f"Error: GPG key '{gpg_key_id}' not found in keyring.", file=sys.stderr)
        for k in private_keys:
            print(f"  Available: {k['fingerprint']} ({k.get('uids', ['?'])[0]})", file=sys.stderr)
        sys.exit(1)
    inrelease = gpg_client.sign(release_text, keyid=gpg_key_id, clearsign=True)
    if not inrelease.data:
        print(f"Error: GPG clearsign failed: {inrelease.stderr}", file=sys.stderr)
        sys.exit(1)
    detached = gpg_client.sign(release_text, keyid=gpg_key_id, detach=True)
    if not detached.data:
        print(f"Error: GPG detached sign failed: {detached.stderr}", file=sys.stderr)
        sys.exit(1)
    return str(inrelease), str(detached)


def export_public_key(gpg_key_id: str, pubkey_file: str | None = None) -> str:
    if pubkey_file:
        path = Path(pubkey_file)
        if not path.is_file():
            print(f"Error: GPG_PUBKEY_FILE not found: {pubkey_file}", file=sys.stderr)
            sys.exit(1)
        return path.read_text()
    gpg_client = gnupg.GPG()
    pubkey = gpg_client.export_keys(gpg_key_id, armor=True)
    if not pubkey:
        print(f"Error: Could not export public key for '{gpg_key_id}'.", file=sys.stderr)
        print("  Set GPG_PUBKEY_FILE=<path/to/audio-tools-repo.gpg.pub> to bypass keyring lookup.", file=sys.stderr)
        sys.exit(1)
    return pubkey


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <path-to-deb> <s3-bucket>", file=sys.stderr)
        sys.exit(1)

    deb_path = sys.argv[1]
    bucket = sys.argv[2]

    if not os.path.isfile(deb_path):
        print(f"Error: .deb file not found: {deb_path}", file=sys.stderr)
        sys.exit(1)

    deb_filename = os.path.basename(deb_path)
    config = load_config()
    dists = config["dists"]
    component = config["component"]
    gpg_key_id = config["gpg_key_id"]
    prefix = config["s3_prefix"]

    print(f"Connecting to {config['s3_endpoint']}...")
    print(f"  Bucket: {bucket}, Prefix: {prefix}")
    s3_client = create_s3_client(config)

    print(f"Analyzing {deb_filename}...")
    metadata = extract_deb_metadata(deb_path)
    package = metadata["Package"]
    version = metadata["Version"]
    arch = metadata["Architecture"]
    pool_path = compute_pool_path(metadata, component, deb_filename)
    metadata["Filename"] = pool_path

    print(f"  Package: {package} {version} [{arch}]")
    print(f"  Pool: {pool_path}")

    if version_exists_in_repo(s3_client, bucket, prefix, config, package, version, arch):
        print(f"\n{package} {version} already exists in the repository. Skipping publish.")
        return

    print(f"\nUploading to s3://{bucket}/{prefix}/...")
    upload_bytes(s3_client, bucket, prefixed_key(prefix, pool_path), Path(deb_path).read_bytes(), "application/vnd.debian.binary-package")

    pubkey_text = export_public_key(gpg_key_id, config["gpg_pubkey_file"])
    upload_text(s3_client, bucket, prefixed_key(prefix, "pubkey.gpg"), pubkey_text)

    for dist in dists:
        print(f"\n--- Publishing to dist: {dist} ---")
        packages_gz_key = f"dists/{dist}/{component}/binary-{arch}/Packages.gz"
        print(f"Fetching existing {packages_gz_key}...")
        existing = download_existing_packages(s3_client, bucket, prefixed_key(prefix, packages_gz_key))
        if existing.strip():
            count = len([b for b in existing.strip().split("\n\n") if b.strip()])
            print(f"  Found {count} existing package(s)")
        else:
            print("  Fresh repository (no existing index)")

        new_entry = build_packages_entry(metadata)
        packages_text = update_packages_content(existing, new_entry, package, version)
        packages_gz_bytes = compress_packages(packages_text)
        dist_config = {**config, "dist": dist}
        release_text = build_release(packages_text, packages_gz_bytes, dist_config, arch)

        print(f"Signing {dist} with GPG key {gpg_key_id}...")
        inrelease_text, release_gpg_text = sign_release(release_text, gpg_key_id, config["gpg_key_file"])

        packages_key = f"dists/{dist}/{component}/binary-{arch}/Packages"
        upload_text(s3_client, bucket, prefixed_key(prefix, packages_key), packages_text)
        upload_bytes(s3_client, bucket, prefixed_key(prefix, packages_gz_key), packages_gz_bytes, "application/gzip")
        upload_text(s3_client, bucket, prefixed_key(prefix, f"dists/{dist}/Release"), release_text)
        upload_text(s3_client, bucket, prefixed_key(prefix, f"dists/{dist}/InRelease"), inrelease_text)
        upload_text(s3_client, bucket, prefixed_key(prefix, f"dists/{dist}/Release.gpg"), release_gpg_text)

    base_url = f"{config['s3_endpoint']}/{bucket}/{prefix}"
    print(f"\nDone! Published {package} {version} to s3://{bucket}/{prefix} (dists: {', '.join(dists)})")
    print("\nClient setup:")
    print(f"  curl -fsSL {base_url}/pubkey.gpg | sudo gpg --dearmor -o /usr/share/keyrings/audio-tools.gpg")
    print(f'  echo "deb [signed-by=/usr/share/keyrings/audio-tools.gpg] {base_url} <dist> {component}" | \\')
    print("    sudo tee /etc/apt/sources.list.d/audio-tools.list")
    print("  sudo apt-get update && sudo apt-get install audio-tools")


if __name__ == "__main__":
    main()
