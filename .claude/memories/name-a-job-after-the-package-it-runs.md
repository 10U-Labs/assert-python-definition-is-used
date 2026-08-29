# Name a job after the package it runs

A CI job that runs a published tool takes that tool's name in full:
`assert-no-comments`, not `no-comments`. The short names the workflow
carried before were not a convention anyone chose, so do not read one out
of the file and extend it.

yamllint runs with `key-ordering: enable`, so a renamed job has to move to
its new alphabetical place under `jobs:` as well.
