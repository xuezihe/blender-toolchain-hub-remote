#!/usr/bin/env bash
set -euo pipefail

RELEASE_TAG="${RELEASE_TAG:-v1.0.0}"
ARTIFACT_BASE_URL="${ARTIFACT_BASE_URL:-https://downloads.example.com/releases/${RELEASE_TAG}}"
MANIFEST_URL="${MANIFEST_URL:-https://static.example.com/blender/manifest.json}"

python scripts/build_repo.py \
  --config publisher.config.json \
  --output-dir dist \
  --artifact-base-url "${ARTIFACT_BASE_URL}"

python scripts/validate_manifest.py \
  --manifest dist/manifest.json \
  --artifacts-dir dist/artifacts

echo "Upload dist/artifacts/* to your release storage here"
echo "Verify the uploaded artifact URLs here"
echo "Publish dist/manifest.json to ${MANIFEST_URL} here"

