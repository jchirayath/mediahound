# Releasing

MediaHound publishes to PyPI automatically via **Trusted Publishing** (OpenID Connect) — no API
tokens are stored in the repo or GitHub secrets. The `.github/workflows/publish.yml` workflow builds
the sdist + wheel and uploads them when a GitHub Release is published.

## One-time setup (on PyPI)

This must be done once by a PyPI account owner, since it requires logging in to PyPI:

1. Sign in at <https://pypi.org>.
2. Go to **Account → Publishing** (<https://pypi.org/manage/account/publishing/>).
3. Under **Add a new pending publisher**, register:
   - **PyPI Project Name:** `mediahound`
   - **Owner:** `jchirayath`
   - **Repository name:** `mediahound`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
4. Save. (A "pending" publisher lets the very first release create the project; after that it becomes
   a normal trusted publisher.)

Optionally, in the GitHub repo, create an **Environment** named `pypi`
(Settings → Environments) and add protection rules (e.g. required reviewers) for extra safety.

## Cutting a release

1. Bump `version` in `pyproject.toml` and add a section to `CHANGELOG.md`.
2. Commit, then tag and create a GitHub Release:
   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   gh release create vX.Y.Z --title "vX.Y.Z — MediaHound" --notes "…"
   ```
3. Publishing the release triggers `publish.yml`, which builds, `twine check`s, and uploads to PyPI.
4. Verify: `pip install mediahound==X.Y.Z` in a clean venv.

To publish the **current** version without a new release (e.g. the first upload after setup), run the
**Publish to PyPI** workflow manually from the Actions tab (`workflow_dispatch`).

## Versioning

MediaHound follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
