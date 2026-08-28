# Fix the measurement rather than adding a flag

When an option exists so that the caller can compensate for evidence the
tool does not trust, the defect is in the evidence. Improve what the tool
measures and the option has nothing left to decide.

`--count-defining-file` was that option. It chose whether a name written
elsewhere in its own defining file counted as a use, and the default was
that it did not. The reasoning was sound as far as it went: uses were
found by searching each file's text for the name as a whole word, and by
that measure a docstring example, an `__all__` entry and a real call are
indistinguishable, so crediting the defining file would have hidden dead
code. The flag let a caller opt into the looser rule when their codebase
could not live with the stricter one.

The cost was that the stricter rule reported two unrelated things in the
same format. A public helper that a live sibling calls, and a definition
nothing anywhere calls, both printed as `path:line:name`. One wants a
leading underscore and the other wants deleting, and the output gave the
reader no way to tell which they were looking at. Every repository this
package gates had to be run twice and the results diffed to separate
them, which is not a thing the output should require.

The unreliability belonged to the measurement, not to same-file use. The
defining file has already been parsed, because parsing it is how its
definitions were found, so `names_in_code` reads its uses from the syntax
tree: a call, a decorator, a default, a base class, an annotation, or a
parameter of that name, which is how a fixture is asked for. Docstrings,
comments and `__all__` entries are constants and count for nothing. Every
other file keeps the blunt whole-word rule in `names_in_text`, which is
what lets the tool work on a repository it cannot import.

The flag then had no question left to ask and was deleted from `cli.py`
and from `action.yml`, and README's "What counts as a use" was rewritten
to argue the new rule where it had argued the old one.

This was written on 2026-08-23, after the flag survived three rounds of
being defended. The defence each time was a situation where a caller
would need the looser rule: a codebase that had not adopted the leading
underscore, a pytest fixture that cannot be renamed, a published library
whose callers are outside the repository. Checked one at a time against
`kms_client` in `lib/python/test_fixtures/aws.py` in the 10ulabs.com
repository, two of the three turned out to be arguments for
`--dont-search-in` rather than for this flag, and the third was a
migration that had not been done yet. None of them was a reason for the
tool to keep asking.
