from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
SUPPORTED_ARTIFACT_TYPES = {"py", "zip"}
SUPPORTED_MANIFEST_VERSION = "1.0"


class PublisherConfigError(ValueError):
    """Raised when publisher.config.json is invalid."""


class PublisherManifestError(ValueError):
    """Raised when a generated manifest is invalid."""


def read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublisherConfigError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PublisherConfigError(f"Invalid JSON in {path}: {exc}") from exc


def validate_identifier(value: str, *, field_name: str) -> str:
    if not value or not ID_PATTERN.fullmatch(value):
        raise PublisherConfigError(
            f"{field_name} must contain only lowercase letters, digits, '_' or '-': {value!r}"
        )
    return value


def is_valid_version(value: str) -> bool:
    if not value:
        return False
    return all(part.isdigit() for part in value.split("."))


def validate_version(value: str, *, field_name: str) -> str:
    if not is_valid_version(value):
        raise PublisherConfigError(f"{field_name} must be a dot-separated integer version: {value!r}")
    return value


def require_string(mapping: dict[str, Any], key: str, *, field_name: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PublisherConfigError(f"{field_name} is required")
    return value.strip()


def optional_string(mapping: dict[str, Any], key: str, *, field_name: str) -> str | None:
    value = mapping.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise PublisherConfigError(f"{field_name} must be a string")
    text = value.strip()
    return text or None


def validate_safe_relative_path(value: str, *, field_name: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        raise PublisherConfigError(f"{field_name} is required")
    if normalized.startswith("/") or normalized.startswith("\\"):
        raise PublisherConfigError(f"{field_name} must be relative: {value!r}")
    if re.match(r"^[A-Za-z]:", normalized):
        raise PublisherConfigError(f"{field_name} must not include a drive prefix: {value!r}")

    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PublisherConfigError(f"{field_name} contains unsafe traversal segments: {value!r}")
    return normalized


def validate_absolute_http_url(value: str, *, field_name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PublisherConfigError(f"{field_name} must be an absolute HTTP(S) URL: {value!r}")
    return value


def normalize_tags(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value in (None, []):
        return []
    if not isinstance(raw_value, list):
        raise PublisherConfigError(f"{field_name} must be a list of strings")
    tags: list[str] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, str) or not item.strip():
            raise PublisherConfigError(f"{field_name}[{index}] must be a non-empty string")
        tags.append(item.strip())
    return tags


def load_publisher_config(config_path: Path) -> dict[str, Any]:
    payload = read_json_file(config_path)
    if not isinstance(payload, dict):
        raise PublisherConfigError("publisher.config.json root must be an object")

    source_payload = payload.get("source")
    if not isinstance(source_payload, dict):
        raise PublisherConfigError("source must be an object")

    source = {
        "source_id": validate_identifier(
            require_string(source_payload, "source_id", field_name="source.source_id"),
            field_name="source.source_id",
        ),
        "name": require_string(source_payload, "name", field_name="source.name"),
    }
    homepage = optional_string(source_payload, "homepage", field_name="source.homepage")
    if homepage is not None:
        source["homepage"] = validate_absolute_http_url(homepage, field_name="source.homepage")

    packages_payload = payload.get("packages")
    if not isinstance(packages_payload, list) or not packages_payload:
        raise PublisherConfigError("packages must be a non-empty list")

    packages: list[dict[str, Any]] = []
    seen_package_ids: set[str] = set()
    for index, package_payload in enumerate(packages_payload):
        if not isinstance(package_payload, dict):
            raise PublisherConfigError(f"packages[{index}] must be an object")

        package_id = validate_identifier(
            require_string(package_payload, "package_id", field_name=f"packages[{index}].package_id"),
            field_name=f"packages[{index}].package_id",
        )
        if package_id in seen_package_ids:
            raise PublisherConfigError(f"Duplicate package_id: {package_id!r}")
        seen_package_ids.add(package_id)

        artifact_type = require_string(package_payload, "artifact_type", field_name=f"packages[{index}].artifact_type")
        if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            raise PublisherConfigError(
                f"packages[{index}].artifact_type must be one of {sorted(SUPPORTED_ARTIFACT_TYPES)}"
            )

        entry_script = validate_safe_relative_path(
            require_string(package_payload, "entry_script", field_name=f"packages[{index}].entry_script"),
            field_name=f"packages[{index}].entry_script",
        )

        package = {
            "package_id": package_id,
            "name": require_string(package_payload, "name", field_name=f"packages[{index}].name"),
            "version": validate_version(
                require_string(package_payload, "version", field_name=f"packages[{index}].version"),
                field_name=f"packages[{index}].version",
            ),
            "artifact_type": artifact_type,
            "source_path": validate_safe_relative_path(
                require_string(package_payload, "source_path", field_name=f"packages[{index}].source_path"),
                field_name=f"packages[{index}].source_path",
            ),
            "entry_script": entry_script,
            "description": require_string(package_payload, "description", field_name=f"packages[{index}].description"),
            "tags": normalize_tags(package_payload.get("tags"), field_name=f"packages[{index}].tags"),
        }

        category = optional_string(package_payload, "category", field_name=f"packages[{index}].category")
        if category is not None:
            package["category"] = category

        author = optional_string(package_payload, "author", field_name=f"packages[{index}].author")
        if author is not None:
            package["author"] = author

        blender_version_min = optional_string(
            package_payload,
            "blender_version_min",
            field_name=f"packages[{index}].blender_version_min",
        )
        if blender_version_min is not None:
            package["blender_version_min"] = validate_version(
                blender_version_min,
                field_name=f"packages[{index}].blender_version_min",
            )

        homepage = optional_string(package_payload, "homepage", field_name=f"packages[{index}].homepage")
        if homepage is not None:
            package["homepage"] = validate_absolute_http_url(homepage, field_name=f"packages[{index}].homepage")

        packages.append(package)

    return {"source": source, "packages": packages}


def validate_manifest_document(manifest_path: Path) -> dict[str, Any]:
    payload = read_json_file(manifest_path)
    if not isinstance(payload, dict):
        raise PublisherManifestError("manifest root must be an object")

    manifest_version = payload.get("manifest_version")
    if manifest_version != SUPPORTED_MANIFEST_VERSION:
        raise PublisherManifestError(f"manifest_version must be {SUPPORTED_MANIFEST_VERSION!r}")

    source_payload = payload.get("source")
    if not isinstance(source_payload, dict):
        raise PublisherManifestError("source must be an object")

    source_id = source_payload.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise PublisherManifestError("source.source_id is required")
    validate_identifier(source_id.strip(), field_name="source.source_id")

    source_name = source_payload.get("name")
    if not isinstance(source_name, str) or not source_name.strip():
        raise PublisherManifestError("source.name is required")

    homepage = source_payload.get("homepage")
    if homepage not in (None, ""):
        if not isinstance(homepage, str):
            raise PublisherManifestError("source.homepage must be a string")
        validate_absolute_http_url(homepage.strip(), field_name="source.homepage")

    packages_payload = payload.get("packages")
    if not isinstance(packages_payload, list):
        raise PublisherManifestError("packages must be a list")

    seen_package_ids: set[str] = set()
    normalized_packages: list[dict[str, Any]] = []
    for index, package_payload in enumerate(packages_payload):
        if not isinstance(package_payload, dict):
            raise PublisherManifestError(f"packages[{index}] must be an object")

        package_id = package_payload.get("package_id")
        if not isinstance(package_id, str) or not package_id.strip():
            raise PublisherManifestError(f"packages[{index}].package_id is required")
        package_id = package_id.strip()
        if not ID_PATTERN.fullmatch(package_id):
            raise PublisherManifestError(f"packages[{index}].package_id is invalid: {package_id!r}")
        if package_id in seen_package_ids:
            raise PublisherManifestError(f"Duplicate package_id: {package_id!r}")
        seen_package_ids.add(package_id)

        name = package_payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise PublisherManifestError(f"packages[{index}].name is required")

        version = package_payload.get("version")
        if not isinstance(version, str) or not is_valid_version(version.strip()):
            raise PublisherManifestError(f"packages[{index}].version is invalid")
        version = version.strip()

        artifact_type = package_payload.get("artifact_type")
        if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            raise PublisherManifestError(
                f"packages[{index}].artifact_type must be one of {sorted(SUPPORTED_ARTIFACT_TYPES)}"
            )

        artifact_url = package_payload.get("artifact_url")
        if not isinstance(artifact_url, str) or not artifact_url.strip():
            raise PublisherManifestError(f"packages[{index}].artifact_url is required")
        artifact_url = validate_absolute_http_url(artifact_url.strip(), field_name=f"packages[{index}].artifact_url")

        artifact_sha256 = package_payload.get("artifact_sha256")
        if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
            raise PublisherManifestError(f"packages[{index}].artifact_sha256 must be 64 lowercase hex chars")

        entry_script = package_payload.get("entry_script")
        if not isinstance(entry_script, str) or not entry_script.strip():
            raise PublisherManifestError(f"packages[{index}].entry_script is required")
        entry_script = validate_safe_relative_path(
            entry_script.strip(),
            field_name=f"packages[{index}].entry_script",
        )

        if artifact_type == "py" and artifact_filename_from_url(artifact_url) != entry_script:
            raise PublisherManifestError(
                f"packages[{index}].entry_script must match the .py artifact filename"
            )

        description = package_payload.get("description")
        if not isinstance(description, str) or not description.strip():
            raise PublisherManifestError(f"packages[{index}].description is required")

        tags = package_payload.get("tags", [])
        if tags is None:
            tags = []
        if not isinstance(tags, list):
            raise PublisherManifestError(f"packages[{index}].tags must be a list")

        blender_version_min = package_payload.get("blender_version_min")
        if blender_version_min not in (None, ""):
            if not isinstance(blender_version_min, str) or not is_valid_version(blender_version_min.strip()):
                raise PublisherManifestError(f"packages[{index}].blender_version_min is invalid")

        homepage = package_payload.get("homepage")
        if homepage not in (None, ""):
            if not isinstance(homepage, str):
                raise PublisherManifestError(f"packages[{index}].homepage must be a string")
            validate_absolute_http_url(homepage.strip(), field_name=f"packages[{index}].homepage")

        normalized_packages.append(
            {
                "package_id": package_id,
                "version": version,
                "artifact_type": artifact_type,
                "artifact_url": artifact_url,
                "artifact_sha256": artifact_sha256,
                "entry_script": entry_script,
            }
        )

    payload["packages"] = normalized_packages
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_relative_under_root(root: Path, relative_path: str, *, field_name: str) -> Path:
    normalized = validate_safe_relative_path(relative_path, field_name=field_name)
    parts = PurePosixPath(normalized).parts
    resolved = root
    for part in parts:
        resolved = resolved / part
    return resolved


def artifact_filename_from_url(artifact_url: str) -> str:
    parsed = urlparse(artifact_url)
    artifact_name = Path(parsed.path).name
    if not artifact_name:
        raise PublisherManifestError(f"artifact_url does not contain a filename: {artifact_url!r}")
    return artifact_name

