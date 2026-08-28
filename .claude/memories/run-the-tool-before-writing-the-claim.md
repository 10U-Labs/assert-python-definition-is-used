# Run the tool before writing the claim into an issue

A claim about what this tool does goes into an issue only after the tool has
been run and the output read. It is a CLI over a directory, so the cost is a
scratch tree and one command.

Issue #1 claimed a name in a `.tf` file keeps a definition alive. It does
not: `_collect` in `cli.py` keeps a path only when it ends in `.py`, over
the definition trees and `search-in:` alike. The reasoning was right about
the matching rule in `scanner.py` and wrong about which files that rule ever
sees, so read the collection step too.

Having found one claim wrong, the pull is to treat whatever it uncovers as
new. The second reading is owed the same test as the first.
