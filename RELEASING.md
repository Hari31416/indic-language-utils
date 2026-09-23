# Release Process and Checklist

This document details the checklist, validation steps, and procedure for releasing a new version of `indic-language-utils`.

## Prerequisites

Before starting a release, verify:

- All intended features, fixes, and docs have been merged to `main`.
- The local working tree is clean (`git status`).
- Required developer tooling is installed: `uv`, `pnpm`, and `python` (>=3.11).

## 1. Version Bumping

Determine the target version adhering to Semantic Versioning (`MAJOR.MINOR.PATCH`).

Update the version number across the following files:

- `pyproject.toml`: Update `version` under `[project]`.
- `web/package.json`: Update `"version"`.
- `web/src/App.tsx`: Update the version badge displayed in the navigation header.
- `uv.lock`: Run `uv lock` to synchronize lockfile resolution with the updated package version.

## 2. Changelog Preparation

Document all user-facing changes in `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/en/1.0.0/):

- Add a new section directly below the header: `## [X.Y.Z] - YYYY-MM-DD`.
- Group entries into appropriate subheadings:
  - `### Added` for new features or capabilities.
  - `### Changed` for modifications to existing functionality.
  - `### Deprecated` for soon-to-be-removed features.
  - `### Removed` for removed features.
  - `### Fixed` for bug fixes.
  - `### Security` for vulnerability fixes.
- Ensure the header strictly matches `## [X.Y.Z]` format, as GitHub Actions release workflows use this regular expression to generate GitHub Release notes.

## 3. Pre-Release Verification Checklist

Execute each verification step locally prior to committing:

### Code Formatting and Linting

Verify formatting and linting pass across the Python codebase:

```bash
uv run ruff format --check .
uv run ruff check .
```

### Static Type Checking

Verify typing across all modules:

```bash
uv run mypy
```

### Test Suite

Run the full pytest suite:

```bash
uv run pytest
```

Ensure unit tests for optional features (such as `aksharamukha`, `ai4bharat-transliteration`, and `fasttext`) handle missing dependencies properly:

- Live conversion tests must have `@pytest.mark.skipif(not HAVE_<FEATURE>, reason="...")` decorators.
- API endpoint tests in `tests/test_server.py` must either mock provider responses or guard live assertions with availability checks.
- When optional libraries are absent, endpoints should return HTTP 400 with a descriptive error.

### Frontend Workbench Build

Compile and build the web workbench assets:

```bash
pnpm --dir web build
```

Verify that `dist/index.html` and assets compile without TypeScript or bundler errors.

### Distribution Artifacts Build

Validate that source distributions and wheels build cleanly:

```bash
uv build
```

### Automated Tag and Changelog Match Check

Validate that the release check script used in `.github/workflows/publish.yml` succeeds:

```bash
python -c '
import re
import tomllib
from pathlib import Path

package_version = tomllib.load(open("pyproject.toml", "rb"))["project"]["version"]
changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
pattern = rf"##\s+\[{re.escape(package_version)}\][\s\S]*?(?=\n##\s+\[|\Z)"
match = re.search(pattern, changelog)
assert match is not None, f"Missing changelog entry for {package_version}"
print(f"Release check passed for version {package_version}")
'
```

## 4. Commit, Tag, and Push

Once all verification steps pass:

### Stage and Commit

Stage only release metadata and documentation files:

```bash
git add pyproject.toml web/package.json web/src/App.tsx uv.lock CHANGELOG.md
```

Commit using conventional commit format:

```bash
git commit -m "chore(general): release version X.Y.Z" \
  -m "- bump version to X.Y.Z in pyproject.toml and web/package.json" \
  -m "- add release notes for X.Y.Z in CHANGELOG.md" \
  -m "- update web workbench header version badge in web/src/App.tsx" \
  -m "- update uv.lock with new package version"
```

### Create Annotated Tag

Create an annotated git tag matching the package version prefixed with `v`:

```bash
git tag -a vX.Y.Z -m "Release X.Y.Z"
```

### Push to Remote

Push the commit and tag to GitHub:

```bash
git push origin main
git push origin vX.Y.Z
```

## 5. Post-Release Verification

After pushing the release tag:

- **GitHub Actions**: Monitor the `Release` workflow triggered by the tag.
- **Workflow Steps**: Ensure the workflow passes the tag-version match check, executes tests, builds artifacts, extracts changelog notes, creates the GitHub Release, and publishes to PyPI via Trusted Publishing.
- **PyPI Release**: Confirm the new version is available on PyPI: `https://pypi.org/p/indic-language-utils`.
- **Documentation**: Verify GitHub Pages docs update automatically via the `Deploy Docs` workflow.
