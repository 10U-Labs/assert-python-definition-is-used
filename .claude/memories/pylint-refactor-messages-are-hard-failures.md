# pylint refactor messages are hard failures

`--fail-on=C,R,W` means pylint's R messages fail the job, so its default
limits are hard limits here: 5 arguments, 15 locals, 12 branches, 50
statements per function. Inline directives are banned, so the only route
is to split the function.

That is why `main` hands its work to `_findings_for` rather than growing
another local for each mode it grew.
