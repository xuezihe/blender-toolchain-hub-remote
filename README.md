# Publisher Starter Template

This template is the first runnable `Publisher Starter` for `Blender Toolchain Hub`.

## Default Flow

1. Put your scripts into `packages/`.
2. Update `publisher.config.json`.
3. Trigger the GitHub `Publish` workflow.

The workflow handles build, validation, release asset upload, artifact URL checks, and `manifest.json` publication for you.

## Repository Layout

```text
repo-template/
  publisher.config.json
  packages/
  scripts/
    build_repo.py
    validate_manifest.py
    publisher_common.py
  .github/workflows/
    publish.yml
  ci-examples/
    shell-runner/
```

## Configuration

`publisher.config.json` is the only source of truth for publisher metadata.

- `source` declares repository-level metadata.
- `packages` declares every package that should be published.
- `source_path` is always explicit.
  - For `py`, it points to a single `.py` file.
  - For `zip`, it points to a directory that will be zipped.

## Local Build

Use the same commands as the CI workflow:

```bash
python scripts/build_repo.py --config publisher.config.json --output-dir dist --artifact-base-url "https://example.com/releases/v1.0.0"
python scripts/validate_manifest.py --manifest dist/manifest.json --artifacts-dir dist/artifacts
```

`build_repo.py` generates:

- `dist/artifacts/`
- `dist/manifest.json`

`validate_manifest.py` re-checks the generated manifest against the local artifact files before you publish anything.

## GitHub Publish

The default workflow lives at `.github/workflows/publish.yml`.

- Primary path: `workflow_dispatch`
- Advanced path: `push tag` matching `v*`

Manual publish requires a `release_tag` input. The workflow then:

1. Builds artifacts and `manifest.json`
2. Validates the generated output
3. Uploads artifacts to GitHub Releases
4. Verifies the public artifact URLs
5. Publishes `manifest.json` to GitHub Pages
6. Writes the final `manifest_url` to the workflow summary

The final `manifest_url` shape is:

```text
https://<owner>.github.io/<repo>/manifest.json
```

## Non-GitHub CI

If your team uses another CI platform, keep the same contract:

1. Run `build_repo.py`
2. Run `validate_manifest.py`
3. Publish artifacts
4. Verify artifact URLs
5. Publish `manifest.json` last

See `ci-examples/shell-runner/` for the provider-agnostic starting point.

