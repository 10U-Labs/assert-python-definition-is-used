# Verify platform capabilities against the API

A claim that a platform cannot do something is a claim about training data,
not about the platform. The knowledge cutoff is earlier than the working
date, and the user tracks releases that fall in the gap.

This was learned by asserting that GitHub had no way to disable pull
requests. The user said otherwise, and `gh api repos/{owner}/{repo}`
returned `has_pull_requests` and `pull_request_creation_policy` in the
response body. The assertion had been confident and had never been checked
against the thing it described.

So a question about what a platform supports is answered by querying the
live API or CLI and reading the response, not from memory. Where the
response settles it, quote the field. Where it does not, the honest phrasing
is that the field is absent from the response, which is a statement about
what was checked rather than about what exists.

See run-the-tool-before-writing-the-claim for the same discipline applied to
this repository's own CLI, and commit-straight-to-main for the working
rule that the GitHub response settled.
