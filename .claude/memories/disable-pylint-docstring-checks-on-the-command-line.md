# Disable pylint's docstring checks on the command line

`assert-no-comments` deletes every docstring, and pylint then reports
`missing-module-docstring`, `missing-class-docstring` and
`missing-function-docstring`, which `--fail-on=C,R,W` treats as failures.
Config files and inline directives are both banned here, so the disables
go on the `pylint` command in the workflow, one `--disable` per message to
stay inside yamllint's 80-column line.
