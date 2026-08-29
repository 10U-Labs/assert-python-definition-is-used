# Name a conftest fixture apart from what it asks for

A fixture that asks for another fixture defined in the same module trips
pylint's `redefined-outer-name`, which `--fail-on=C,R,W` treats as a
failure. Inline directives are banned here, so the only route is to name
the function apart from the fixture: `@pytest.fixture(name="run_over")` on
`def run_over_fixture(write_tree, run_cli)`. The parameter then shadows
nothing. This only bites inside a conftest; a test module has no
module-level name to shadow.
