# Generic Shell Runner Example

This directory shows the provider-agnostic publish sequence for teams that do not use GitHub Actions as their primary CI.

Keep the same order:

1. Run `build_repo.py`
2. Run `validate_manifest.py`
3. Upload artifacts
4. Verify artifact URLs
5. Publish `manifest.json` last

The sample shell script is intentionally incomplete around provider-specific upload and deployment commands. Replace those placeholders with your CI platform's release storage and static hosting steps.

