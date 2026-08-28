# assert-python-definition-is-used

Assert that every public Python definition in a tree is named somewhere
else.

## Why

A function whose last caller is deleted does not disappear. Its tests
still pass, the coverage gate over its module stays green, and static
analysis keeps reading it, so the tree grows a layer of code that is
maintained and never called. Nothing in a normal toolchain reports it:
coverage measures whether lines run, not whether anything wants them,
and a module held at 100% by its own tests manufactures exactly the
evidence that makes it look used.

This tool asks the other question. For every public top-level `def` and
`class` in the trees you point it at, it asks whether anything else
names it, and reports the ones nothing does.

## Installation

```bash
pip install assert-python-definition-is-used
```

## Usage

```bash
# Every definition in lib/python must be named somewhere in the repo
assert-python-definition-is-used lib/python \
  --search-in lib/python --search-in scripts \
  --search-in src --search-in test

# The same, but a module's own tests no longer count as a caller
assert-python-definition-is-used lib/python \
  --search-in lib/python --search-in scripts \
  --search-in src --search-in test \
  --dont-search-in 'test/lib/python/test_{package}'
```

Those two runs are the pair worth having. The first is a cheap outer
bound that catches a definition whose tests were deleted along with its
caller. The second is the one that finds code kept alive only by the
tests written for it, which is what a coverage gate hides.

### Options

| Option | Effect |
| --- | --- |
| `--search-in PATH` | A tree to search for uses. Repeatable. |
| `--dont-search-in TEMPLATE` | Template left out of the search. |
| `--exclude PATTERNS` | Comma-separated globs to leave out of both trees. |
| `--assume-used-matching PATTERNS` | Globs of names a runtime invokes. |
| `--assume-used-decorated-with PATHS` | Decorators a runtime invokes. |
| `--quiet` | Print nothing; report through the exit code. |
| `--count` | Print only how many findings there were. |
| `--verbose` | Print each file scanned, each one read as text, and a summary. |
| `--fail-fast` | Stop at the first finding. |
| `--warn-only` | Always exit 0. |

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Nothing unused |
| 1 | Something unused |
| 2 | A tree was missing, unreadable, or would not parse |

## What counts as a use

Every file these trees reach is a Python file, so every one of them is
read as code rather than as text. A use is the definition's name read by
a file's syntax tree: a call, a decorator, a default, a base class, an
annotation, an attribute, an import, or a parameter of that name, which
is how a fixture is asked for. A name written in a string constant is a
use too, because that is how a name crosses a file boundary as data, the
way a Django route reaches a view.

A comment is not a use. The parser discards it, so a note saying a call
was removed cannot keep alive the definition it names. A docstring and an
`__all__` entry are not uses either: both are prose about a definition
rather than a use of it, and crediting them would leave a dead definition
unreported. A re-export still reads as used, because the `__all__` entry
naming a definition comes with the import that brings it in, and an
import is a read. A `def` or `class` statement binds its name without
reading it, so nothing counts as its own use.

The file a definition lives in is read no differently from any other. A
function its own file calls is a helper doing its job, and reporting it
would be wrong; one its own file only writes about is not used by it.

A file that will not parse falls back to a whole-word search over its raw
text, where a name written anywhere, in code or in prose, counts. A
repository holding a file Python cannot read keeps the blunt rule on that
file rather than failing, and `--verbose` names each file that fell back.

Reading a name is still not resolving it. A file that calls its own
unrelated function of the same name counts as a use, so the count is a
lower bound rather than an exact figure.

Two dead functions in one file that call each other still read as used,
because those calls are real code. Finding those needs reachability from
a live entry point, which is a different tool.

Only top-level `def` and `class` statements are read. A method and a
nested function are reached through the name of the thing that holds
them, so neither is something this tool can speak about. Names starting
with an underscore are skipped.

## Definitions a runtime invokes

A use has to be written down somewhere for the search to find it, and
some definitions are never written down. pytest finds a test by scanning
a directory and matching a prefix, so a test function's name appears
nowhere but its own `def` line. The same goes for a `pytest_` hook the
plugin manager calls, for a fixture asked for under the name in its
decorator, and for a Flask view or a Lambda handler reached from outside
Python. Pointed at a test tree, the tool reports every test in it.

Two options let you name those definitions so the tool leaves them alone.
Both default to empty, so a run passing neither answers exactly as it did
before.

`--assume-used-matching` takes globs matched against a definition's name.
`--assume-used-decorated-with` takes dotted paths matched against the
decorators a definition carries, so `pytest.fixture` matches
`@pytest.fixture` and `@pytest.fixture(name="x")` alike. A definition
either one matches is neither searched for nor reported, and `--verbose`
says how many each took out, so a pattern matching more than you meant is
visible rather than silent.

Neither option knows what pytest is. A repository running pytest says so
itself:

```bash
assert-python-definition-is-used test \
  --search-in test \
  --assume-used-matching 'test_*,Test*,pytest_*' \
  --assume-used-decorated-with pytest.fixture
```

One running Flask passes `--assume-used-decorated-with app.route`, one
running Celery passes `task`, and one deploying to Lambda passes
`--assume-used-matching lambda_handler`.

## Packages and their own tests

The usual thing to leave out is a package's own tests, and
`--dont-search-in` takes a path template rather than a fixed layout,
because the convention differs between repositories. The `{package}`
field is the first directory below the definition tree:

```text
lib/python/aws_clients/__init__.py  ->  package is "aws_clients"
```

So `--dont-search-in 'test/lib/python/test_{package}'` leaves out
`test/lib/python/test_aws_clients/`, and
`--dont-search-in 'test/lib/python/{package}'` leaves out
`test/lib/python/aws_clients/`.

A file sitting directly in the definition tree belongs to no package
and so has no directory of its own to leave out. Uses of its definitions
count wherever they appear.

`--dont-search-in` is not `--exclude`. An excluded file is dropped from
the run altogether, so its own definitions go unchecked too. A file left
out of the search is still read for the definitions it holds; it just
does not get a vote on whether anything else is used.

## GitHub Actions

```yaml
- name: Assert every definition is used outside its own tests
  uses: 10U-Labs/assert-python-definition-is-used@latest
  with:
    dont-search-in: test/lib/python/test_{package}
    search-in: lib/python scripts src test
    trees: lib/python
    verbose: true
```

Over a test tree, name what pytest invokes:

```yaml
- name: Assert every test helper is used
  uses: 10U-Labs/assert-python-definition-is-used@latest
  with:
    assume-used-decorated-with: pytest.fixture
    assume-used-matching: test_*,Test*,pytest_*
    search-in: test
    trees: test
    verbose: true
```

## License

Apache-2.0
