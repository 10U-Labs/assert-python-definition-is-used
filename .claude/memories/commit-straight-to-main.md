# Commit straight to main

Work in this repository is committed to `main` and pushed. There are no
other branches and no merge commits in the history, so branching before a
commit builds a branch nothing will ever merge, and offering a pull request
offers something the repository has switched off: `has_pull_requests` is
false for `10U-Labs/assert-python-definition-is-used`, set on 2026-08-22.

The habit being corrected is the branch-and-PR reflex carried in from other
repositories. It is not a house style question here. A pull request cannot
be opened at all, and a topic branch is a dead end.

Push each commit as it is made rather than letting `main` run ahead of
`origin/main`, since there is no branch holding the work in the meantime.
See verify-platform-capabilities-against-api for how the GitHub setting was
found, which is a separate lesson about checking claims against the live
API.
