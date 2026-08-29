# Let CI run the checks

Never run locally what CI runs, and do not wait on a run after pushing.
Every job is free on GitHub and costs Claude tokens here. Push and let the
workflow report.

That covers pytest, mypy, pylint, jscpd, the assert-* tools and `gh run
watch`.
