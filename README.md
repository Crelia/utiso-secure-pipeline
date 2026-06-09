# utiso-secure-pipeline

A small FastAPI service that exists to demonstrate a **security-focused CI/CD
pipeline** on GitHub Actions. The application is intentionally minimal — the
interesting work is in `.github/workflows/`.

## The application

A JSON API with three endpoints:

| Method | Path        | Purpose                                  |
| ------ | ----------- | ---------------------------------------- |
| GET    | `/healthz`  | Liveness check (used by the Docker HEALTHCHECK) |
| GET    | `/version`  | Build version + git SHA                  |
| POST   | `/api/hash` | Returns the SHA-256 of bounded input     |

The app applies conservative security headers to every response (`nosniff`,
`X-Frame-Options: DENY`, a locked-down CSP since it never serves HTML, no
referrer leakage) and bounds request input to avoid trivial resource abuse.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                      # run the tests
uvicorn app.main:app --reload   # http://127.0.0.1:8000/healthz
```

Or with Docker:

```bash
docker build -t utiso-secure-pipeline .
docker run --rm -p 8000:8000 utiso-secure-pipeline
```

## The pipeline

Three workflows, each scoped to least privilege (`permissions: contents: read`
at the top, widened per-job only where required).

### `ci.yml` — runs on every PR and push to `main`
- **lint-and-test** — `ruff` (lint + format check) and `pytest`.
- **secret-scan** — `gitleaks` over full history, so a secret committed and
  later "removed" is still caught.
- **dependency-scan** — `trivy fs` for known-vulnerable dependencies and
  config issues; fails on HIGH/CRITICAL with a fix available.

### `codeql.yml` — SAST
GitHub's CodeQL with the `security-extended` query pack. Runs on PRs, on `main`,
and weekly on a schedule so newly published rules are applied to existing code.
Results land in the repo's **Security** tab.

### `release.yml` — build, scan, publish, sign, attest (deploy)
On push to `main` (and version tags):
1. Build the image and **load it locally**.
2. **Scan with Trivy and fail closed** — a HIGH/CRITICAL vuln stops the image
   from ever being published.
3. Push to the GitHub Container Registry (GHCR).
4. **Sign keylessly with cosign** via OIDC — identity comes from the workflow's
   short-lived token and is logged to the Rekor transparency log; no signing
   key is stored in the repo.
5. **Attest SLSA build provenance** and a **CycloneDX SBOM**, both pushed to the
   registry alongside the image.

"Deploy" here means publishing a signed, attested container image to GHCR. The
image is verifiable end-to-end (the GHCR package must be public for an anonymous
pull; note the image path is lowercase):

```bash
cosign verify ghcr.io/crelia/utiso-secure-pipeline:latest \
  --certificate-identity-regexp "https://github.com/Crelia/utiso-secure-pipeline/.*" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

## Security reasoning (the short version)

Two layers, deliberately:

- **Securing the code** — SAST (CodeQL), SCA (Trivy), secret scanning
  (gitleaks), and container scanning (Trivy) catch vulnerable code, dependencies,
  leaked credentials, and vulnerable base images respectively.
- **Securing the supply chain / the repo itself** — this is the part that's easy
  to skip. The workflow token is read-only by default; actions are pinned (see
  below); the registry login uses the ephemeral `GITHUB_TOKEN`; signing uses
  OIDC instead of a long-lived key; and every image ships with provenance + an
  SBOM so a consumer can verify *what* they're running and *where it came from*.
  Dependabot keeps deps, action pins, and the base image patched.

## Repository settings that complete the picture

These live in repo settings, not in YAML, and should be enabled:
- **Branch protection** on `main`: require PR review, require CI + CodeQL to
  pass, no force-push.
- **Require signed commits**.
- Secret scanning + push protection (on by default for public repos).
- Restrict Actions to the workflows in this repo + verified creators.

## Action pinning and maintenance

Third-party Actions are pinned to full commit SHAs with a trailing version
comment, for example:

```yaml
uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
```

The SHA is the security control: it points to immutable code, so a compromised or
re-tagged `@v6` cannot silently change what this pipeline runs. The comment keeps
the workflow readable for humans. Dependabot's `github-actions` updater keeps
those pins current by opening PRs that move the SHA and update the version
comment together.

## Looking ahead (knowingly simplified for this exercise)

- **Pin the base image by digest**, not tag; add hash-pinned Python deps
  (`pip install --require-hashes`).
- Trivy gates *at build time*; production would add **runtime scanning and an
  admission controller** (e.g. policy that refuses unsigned images via cosign
  verification).
- Move from `GITHUB_TOKEN` to a **dedicated secrets manager** (Vault/cloud KMS)
  with OIDC for any real credentials, and rotate on a schedule.
- An **Ansible** role to harden and reproducibly configure the runner/host with
  secure defaults (the team uses Ansible; CIS-style baseline).
- DAST against the running container, and SLSA Level 3 with a hardened,
  ephemeral builder.
