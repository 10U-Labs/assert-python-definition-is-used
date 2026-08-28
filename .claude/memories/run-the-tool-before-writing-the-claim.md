# Run the tool before writing the claim into an issue

Issue #1 argued that a runtime-invoked definition already passes without the
tool knowing anything about the runtime, and gave `lambda_handler` named by
`handler = "handler.lambda_handler"` in a Terraform file as the case that
proves it. The claim was reasonable from the code that was read: the
cross-file rule in `names_in_text` is a whole-word search over raw text, and
a whole-word search does reach inside a string in a `.tf` file.

It reaches nothing, because the file is never opened. `_collect` in `cli.py`
keeps a collected path only when it ends in `.py`, and that filter runs over
the definition trees and over `search-in:` alike. Two files in a scratch
directory and one run of the CLI showed the definition reported as unused
with the Terraform file sitting in the searched tree. The reasoning had been
correct about the rule and wrong about which files the rule ever sees.

The reading that produced the error was of `scanner.py`, which is where the
matching lives and where the argument was formed. What decides the answer is
a filter one file away, in the collection step, and reading the matcher
carefully is exactly what makes that filter easy not to look for.

So a claim about what this tool does goes into an issue only after the tool
has been run and the output pasted next to it. It is a CLI over a directory,
so the cost is a scratch tree and one command, and that is cheaper than an
issue whose central example argues for the wrong thing. The same run also
settled two claims in issue #2 that would otherwise have been assertions: a
name inside a Python string keeps a definition alive, and a name in a bare
comment does too.

This was written on 2026-08-28, after the Terraform paragraph was corrected
in place. The correction was then itself over-called: the gap it revealed
was written up as wanting an issue of its own, when a definition invoked
from outside written Python is the thing issue #1 already proposes to
answer, and `assume-used-matching: lambda_handler` answers it in the same
terms as pytest. Having found one claim wrong, the pull is to treat what it
uncovers as new, and the second reading is owed the same test as the first.
