# Disabling pull requests

GitHub repositories carry a `has_pull_requests` boolean alongside
`has_issues` and `has_wiki`, and a separate `pull_request_creation_policy`
string, seen holding `all`. The user reports the toggle was added in
response to the growth of GenAI coding assistants.

It is turned off for `10U-Labs/assert-python-definition-is-used`, set on
2026-08-22 with:

```sh
gh api -X PATCH repos/{owner}/{repo} -F has_pull_requests=false
```

`pull_request_creation_policy` stayed `all` through that change, so the two
appear to be separate axes rather than one setting read two ways.

The practical consequence for work in this repository is that changes are
committed straight to `main`. There are no other branches and no merge
commits in the history, so branching before a commit here builds a branch
that nothing will ever merge, and offering a pull request is offering
something the repository has switched off. See
verify-platform-capabilities-against-api for how the fields were found.
