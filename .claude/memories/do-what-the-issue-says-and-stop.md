# Do what the issue says and stop

An issue asking for a CI job means add the job. It does not authorise
rewriting the tree the job will check, however clearly the job will fail
on it. Push the job and let the run report; the cleanup is a separate
issue and a separate decision.

Learned on #5, where adding `no-comments` led to stripping every
docstring out of `src/` and `test/` before the job had ever run.
