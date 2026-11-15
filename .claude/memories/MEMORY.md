# Memories

- [Ask gh before saying GitHub cannot](ask-gh-before-saying-github-cannot.md) — check with `gh api` before saying GitHub cannot do something.
- [Commit straight to main](commit-straight-to-main.md) — commit to main and push; no branches or pull requests.
- [Cover new source in both tiers](cover-new-source-in-both-tiers.md) — every new branch in src/ needs a unit and an integration test; each tier demands 100% coverage alone.
- [Do not offer a pointless choice](do-not-offer-a-pointless-choice.md) — where the options differ in nothing the user cares about, pick one and say which.
- [jscpd reads a docstring as ordinary tokens](jscpd-reads-a-docstring-as-ordinary-tokens.md) — matching docstrings can clone; move the shared body into a helper rather than rewording.
- [Let CI run the checks](let-ci-run-the-checks.md) — never run locally what CI runs, and do not wait on a run after pushing.
- [Name a conftest fixture apart from what it asks for](name-a-conftest-fixture-apart-from-what-it-asks-for.md) — use `@pytest.fixture(name=...)` to dodge pylint's redefined-outer-name.
- [Name a job after the package it runs](name-a-job-after-the-package-it-runs.md) — a CI job takes the tool's full name and sits in alphabetical order under jobs:.
- [pylint refactor messages are hard failures](pylint-refactor-messages-are-hard-failures.md) — R messages fail the job, so split a function that hits pylint's default limits.
- [Run the tool before writing the claim into an issue](run-the-tool-before-writing-the-claim.md) — run it and read the output before describing it in an issue.
- [Start over when the user does not understand](start-over-when-the-user-does-not-understand.md) — go back to the smallest concrete example, in plain words without jargon.
