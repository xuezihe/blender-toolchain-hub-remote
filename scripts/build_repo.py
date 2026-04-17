from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urljoin
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from publisher_common import (
    PublisherConfigError,
    load_publisher_config,
    resolve_relative_under_root,
    sha256_file,
    utc_now_iso,
    validate_absolute_http_url,
)


FIXED_ZIP_TIMESTAMP = (2024, 1, 1, 0, 0, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build publisher artifacts and dist/manifest.json")
    parser.add_argument("--config", required=True, help="Path to publisher.config.json")
    parser.add_argument("--output-dir", required=True, help="Directory for generated dist output")
    parser.add_argument(
        "--artifact-base-url",
        required=True,
        help="Public HTTP(S) base URL where uploaded artifacts will be hosted",
    )
    return parser.parse_args()


def ensure_clean_output_dir(output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def build_artifact_url(base_url: str, artifact_name: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", quote(artifact_name))


def build_python_artifact(package: dict[str, object], repo_root: Path, artifacts_dir: Path) -> tuple[str, Path]:
    source_path = resolve_relative_under_root(
        repo_root,
        str(package["source_path"]),
        field_name=f"packages[{package['package_id']}].source_path",
    )
    if not source_path.is_file():
        raise PublisherConfigError(f"Python source_path does not exist or is not a file: {source_path}")
    if source_path.suffix.lower() != ".py":
        raise PublisherConfigError(f"Python source_path must point to a .py file: {source_path}")

    entry_script = str(package["entry_script"])
    if source_path.name != entry_script:
        raise PublisherConfigError(
            f"Package {package['package_id']!r} entry_script must match source_path basename for .py artifacts"
        )

    artifact_path = artifacts_dir / entry_script
    shutil.copy2(source_path, artifact_path)
    return entry_script, artifact_path


def build_zip_artifact(package: dict[str, object], repo_root: Path, artifacts_dir: Path) -> tuple[str, Path]:
    source_path = resolve_relative_under_root(
        repo_root,
        str(package["source_path"]),
        field_name=f"packages[{package['package_id']}].source_path",
    )
    if not source_path.is_dir():
        raise PublisherConfigError(f"ZIP source_path does not exist or is not a directory: {source_path}")

    entry_script = str(package["entry_script"])
    if not entry_script.endswith(".py"):
        raise PublisherConfigError(f"ZIP package entry_script must point to a .py file: {entry_script!r}")

    entry_script_path = resolve_relative_under_root(
        source_path,
        entry_script,
        field_name=f"packages[{package['package_id']}].entry_script",
    )
    if not entry_script_path.is_file():
        raise PublisherConfigError(
            f"ZIP package entry_script does not exist inside source_path: {entry_script!r}"
        )

    artifact_name = f"{package['package_id']}.zip"
    artifact_path = artifacts_dir / artifact_name
    create_deterministic_zip(source_path, artifact_path)
    return artifact_name, artifact_path


def create_deterministic_zip(source_dir: Path, artifact_path: Path) -> None:
    with ZipFile(artifact_path, "w", compression=ZIP_DEFLATED) as zip_handle:
        file_paths = sorted(
            (path for path in source_dir.rglob("*") if path.is_file()),
            key=lambda item: item.relative_to(source_dir).as_posix(),
        )
        for file_path in file_paths:
            relative_path = PurePosixPath(file_path.relative_to(source_dir).as_posix())
            zip_info = ZipInfo(relative_path.as_posix())
            zip_info.date_time = FIXED_ZIP_TIMESTAMP
            zip_info.compress_type = ZIP_DEFLATED
            zip_info.external_attr = 0o644 << 16
            zip_handle.writestr(zip_info, file_path.read_bytes())


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    repo_root = config_path.parent
    output_dir = Path(args.output_dir).resolve()
    artifact_base_url = validate_absolute_http_url(args.artifact_base_url, field_name="--artifact-base-url")

    config = load_publisher_config(config_path)
    artifacts_dir = ensure_clean_output_dir(output_dir)

    source = dict(config["source"])
    source["generated_at"] = utc_now_iso()

    manifest_packages: list[dict[str, object]] = []
    for package in config["packages"]:
        if package["artifact_type"] == "py":
            artifact_name, artifact_path = build_python_artifact(package, repo_root, artifacts_dir)
        else:
            artifact_name, artifact_path = build_zip_artifact(package, repo_root, artifacts_dir)

        package_record = {
            "package_id": package["package_id"],
            "name": package["name"],
            "version": package["version"],
            "artifact_type": package["artifact_type"],
            "artifact_url": build_artifact_url(artifact_base_url, artifact_name),
            "artifact_sha256": sha256_file(artifact_path),
            "entry_script": package["entry_script"],
            "description": package["description"],
        }

        if package["tags"]:
            package_record["tags"] = package["tags"]
        if "category" in package:
            package_record["category"] = package["category"]
        if "author" in package:
            package_record["author"] = package["author"]
        if "blender_version_min" in package:
            package_record["blender_version_min"] = package["blender_version_min"]
        if "homepage" in package:
            package_record["homepage"] = package["homepage"]

        manifest_packages.append(package_record)

    manifest = {
        "manifest_version": "1.0",
        "source": source,
        "packages": manifest_packages,
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Built {len(manifest_packages)} package(s)")
    print(f"Artifacts directory: {artifacts_dir}")
    print(f"Manifest path: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PublisherConfigError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

