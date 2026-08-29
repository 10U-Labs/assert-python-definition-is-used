# Let CI run the checks

Do not run this repository's CI jobs locally, and do not wait on a run
after pushing. Every job is free on GitHub and costs Claude tokens here.
Push and let the workflow report.

That covers pytest, mypy, pylint, jscpd, the assert-* tools and `gh run
watch`. Run one only where the user asks for it, or where a change cannot
be written without reading the tool's output first.
