## 1. Overview

This repository is a deliberately small FastAPI service used to demonstrate a
security-focused CI/CD pipeline in GitHub Actions. The app exposes a health check,
a version endpoint, and a bounded SHA-256 hashing endpoint. Keeping the app tiny
is a deliberate tradeoff, not a shortcut: it let me make the pipeline thorough —
two layers, securing the code and securing the supply chain — without it becoming
sprawling. The exercise evaluates the pipeline and the security choices, not
application complexity.

I created three workflows:

- `.github/workflows/ci.yml` runs on pushes and pull requests to `main`. It runs
  Ruff formatting/linting, pytest, a gitleaks secret scan over full git history,
  and a Trivy filesystem scan for dependency/configuration issues.
- `.github/workflows/codeql.yml` runs CodeQL SAST for Python on pushes, pull
  requests, and a weekly schedule so new CodeQL rules are applied to existing
  code.
- `.github/workflows/release.yml` is the deploy path. It builds the container,
  scans the image before publishing, pushes it to GitHub Container Registry,
  signs it keylessly with cosign/OIDC, and attaches SLSA provenance plus a
  CycloneDX SBOM attestation.

I also configured Dependabot for Python dependencies, GitHub Actions, and the
Docker base image so pinned dependencies and pinned Actions stay maintainable.

## 2. Security

The pipeline has two security layers.

First, it secures the code and artifact:

- Ruff catches style issues and common Python mistakes, including the Bandit `S`
  ruleset for lightweight security linting.
- pytest gives a regression check for the API behavior and security headers.
- gitleaks detects committed secrets, including secrets that were committed and
  removed later because the checkout uses full history.
- Trivy filesystem scanning checks dependencies and configuration for known
  vulnerabilities.
- CodeQL performs deeper static analysis of the Python source code.
- Trivy image scanning checks the built container image before it is pushed. The
  release gate is fail-closed for fixable HIGH/CRITICAL vulnerabilities.

Second, it secures the supply chain:

- Workflows default to `permissions: contents: read`; only the release and CodeQL
  jobs widen permissions, and only for the specific capabilities they need.
- Third-party Actions are pinned to commit SHAs instead of mutable tags.
- The registry login uses GitHub's ephemeral `GITHUB_TOKEN`, not a stored
  registry password.
- cosign signs the image keylessly using GitHub OIDC, so there is no long-lived
  signing key to store or rotate.
- SLSA provenance records where and how the image was built.
- The SBOM records what is inside the image.
- Dependabot keeps dependencies, Action pins, and the base image patched.

On the repository itself, I enabled branch protection on `main`: changes must go
through a pull request, the CI and CodeQL checks (lint/test, secret scan,
dependency scan, CodeQL analysis) must pass before merging, and force-pushes and
branch deletion are blocked. GitHub secret scanning with push protection is on by
default for public repositories.

Additional settings I would still add are required signed commits (once commit
signing is set up, so it does not block existing unsigned history), and a
restricted Actions policy so only trusted Actions can run.

## 3. AI usage

I used AI tooling as a pair-programming and review aid while building this repository. Specifically, I used Anthropic Claude via Claude Code and OpenAI GPT-5.5 to help brainstorm the pipeline design, review workflow structure, draft documentation, and sanity-check security tradeoffs.

I treated AI output as draft material rather than as final authority. I reviewed the workflows, tested the repository, confirmed the Actions ran successfully, verified the image was published to GHCR, and made the final implementation decisions myself.

AI was most useful for:
- comparing security controls that would fit the scope of the challenge without overbuilding it;
- iterating on GitHub Actions workflow structure;
- reviewing README/ANSWERS wording for clarity;
- helping troubleshoot small implementation issues during development.

One concrete example: the release gate caught a fixable HIGH/CRITICAL dependency vulnerability before publishing. I reviewed the finding, updated the dependency, and reran the pipeline to confirm the gate behaved as intended.

I intentionally kept the application small so I can read, explain, and defend every line during a walkthrough.

## 4. Looking ahead

For a production version or with another week, I would harden several areas that
are intentionally simplified here:

- Pin the Docker base image by digest instead of tag.
- Use hash-pinned Python dependencies with `pip --require-hashes`.
- Add runtime controls, such as admission policy that verifies cosign signatures
  before an image can run.
- Add DAST against the running service.
- Use an external secrets manager, such as Vault or cloud KMS, for any real
  credentials, ideally with OIDC-based access instead of stored keys.
- Move toward SLSA Level 3 with a hardened, ephemeral builder.
- Add an Ansible role or similar host-hardening automation for runner or
  deployment infrastructure.

I intentionally did not add all of that for the take-home because the prompt
asked for a small, clean pipeline that can be built in a few hours.

## 5. Anything else

The release workflow is the part I would highlight most: it scans before pushing,
publishes to GHCR only after the scan passes, signs the immutable image digest,
and attaches verifiable provenance and SBOM data. That demonstrates both CI/CD
mechanics and software supply-chain security without making the demo application
unnecessarily complex.

Two things from building this show the controls are real rather than decorative.
The fail-closed image scan actually blocked a publish over CVE-2024-47874 before
I fixed the dependency, so the gate is doing work, not just present. And
Dependabot's grouping behaved as configured: it bundled low-risk minor/patch
updates into one pull request while isolating a major version bump into its own,
so routine maintenance stays low-noise but breaking changes still get individual
review.
