# Fix the measurement rather than adding a flag

When a flag asks the caller to say whether the tool's own answer can be
trusted, the answer is what needs fixing. Fix it and the flag has nothing
left to decide.

`--count-defining-file` was that flag. The tool searched the defining file's
text for the name, where a docstring, a comment and an `__all__` entry read
exactly like a call, so it could not tell a use from a mention and handed
the caller the choice: count that file or ignore it whole. Neither answer
was right, because a helper its own module calls is used and a dead one its
own module only writes about is not.

The file was already parsed, since parsing is how its definitions were
found. `names_in_code` reads uses from that syntax tree, so a call counts
and a docstring does not, and the flag was deleted.
