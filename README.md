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
| `--count-defining-file` | Count a use in the defining file. |
| `--exclude PATTERNS` | Comma-separated globs to leave out of both trees. |
| `--quiet` | Print nothing; report through the exit code. |
| `--count` | Print only how many findings there were. |
| `--verbose` | Print the trees read, each file scanned, and a summary. |
| `--fail-fast` | Stop at the first finding. |
| `--warn-only` | Always exit 0. |

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Nothing unused |
| 1 | Something unused |
| 2 | A tree was missing, unreadable, or would not parse |

## What counts as a use

A use is the definition's name written as a whole word in any file the
searched trees reach. That is deliberately blunt, and it has two
consequences worth knowing before you read the output.

By default a name written elsewhere in its own defining file does not
count. A docstring example, an `__all__` entry and a call from a
sibling that is itself dead all look the same as a live caller, so
crediting them hides real findings. Pass `--count-defining-file` for the
looser rule. When the stricter rule reports a definition that a live
sibling in the same file genuinely calls, the finding is that the
definition is public and should not be: rename it with a leading
underscore, which takes it out of scope.

Matching on a bare name also means a definition reads as used when any
other file happens to contain that word, including a file that defines
its own unrelated function of the same name. The count is a lower bound
rather than an exact figure.

Only top-level `def` and `class` statements are read. A method and a
nested function are reached through the name of the thing that holds
them, so neither is something this tool can speak about. Names starting
with an underscore are skipped.

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

## License

Apache-2.0
