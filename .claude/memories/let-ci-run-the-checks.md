# Let CI run the checks, and watch the run

Never run locally what CI runs: pytest, mypy, pylint, jscpd and the
assert-* tools. Every job is free on GitHub and costs Claude tokens here.
Push and let the workflow report.

After pushing, watch the run to the end (`gh run watch --exit-status`,
in the background) and fix whatever fails. Do not call the work done
before the run is green.
