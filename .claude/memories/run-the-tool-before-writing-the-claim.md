# Run the tool before writing the claim into an issue

Before writing into an issue what this tool does, run it and read the
output. It is a CLI over a directory, so the cost is a scratch tree and one
command. Issue #1 says a name in a `.tf` file keeps a definition alive.
Run it and nothing does: `_collect` in `cli.py` drops every path that does
not end in `.py`.
