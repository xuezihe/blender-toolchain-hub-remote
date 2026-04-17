from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZipFile

from publisher_common import (
    PublisherConfigError,
    PublisherManifestError,
    artifact_filename_from_url,
    resolve_relative_under_root,
    sha256_file,
    validate_manifest_document,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dist/manifest.json against local artifact files")
    parser.add_argument("--manifest", required=True, help="Path to dist/manifest.json")
    parser.add_argument("--artifacts-dir", required=True, help="Path to dist/artifacts")
    return parser.parse_args()


def validate_zip_entry(artifact_path: Path, entry_script: str) -> None:
    if not entry_script.endswith(".py"):
        raise PublisherManifestError(f"ZIP entry_script must point to a .py file: {entry_script!r}")

    with ZipFile(artifact_path, "r") as zip_handle:
        names = {member.filename.replace("\\", "/") for member in zip_handle.infolist() if not member.is_dir()}
        if entry_script not in names:
            raise PublisherManifestError(
                f"ZIP artifact {artifact_path.name!r} does not contain entry_script {entry_script!r}"
            )


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    if not artifacts_dir.is_dir():
        raise PublisherManifestError(f"Artifacts directory does not exist: {artifacts_dir}")

    manifest = validate_manifest_document(manifest_path)
    for package in manifest["packages"]:
        artifact_name = artifact_filename_from_url(package["artifact_url"])
        artifact_path = artifacts_dir / artifact_name
        if not artifact_path.is_file():
            raise PublisherManifestError(
                f"Artifact file is missing for package {package['package_id']!r}: {artifact_path}"
            )

        expected_sha = package["artifact_sha256"]
        actual_sha = sha256_file(artifact_path)
        if actual_sha != expected_sha:
            raise PublisherManifestError(
                f"Artifact hash mismatch for package {package['package_id']!r}: expected {expected_sha}, got {actual_sha}"
            )

        if package["artifact_type"] == "py":
            if artifact_path.name != package["entry_script"]:
                raise PublisherManifestError(
                    f".py package {package['package_id']!r} entry_script must match artifact filename"
                )
        else:
            resolve_relative_under_root(
                Path("."),
                package["entry_script"],
                field_name=f"packages[{package['package_id']}].entry_script",
            )
            validate_zip_entry(artifact_path, package["entry_script"])

    print(f"Validated manifest: {manifest_path}")
    print(f"Validated artifacts directory: {artifacts_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PublisherConfigError, PublisherManifestError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
