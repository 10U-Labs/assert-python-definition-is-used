# Fix the measurement rather than adding a flag

When an option exists so the caller can compensate for evidence the tool
does not trust, the defect is in the evidence. Improve what the tool
measures and the option has nothing left to decide.

`--count-defining-file` was that option, and it was deleted by parsing the
defining file instead of searching its text: `names_in_code` reads uses from
the syntax tree, so a docstring, a comment and an `__all__` entry no longer
look like a call. It was defended three times with cases where a caller
would need the looser rule, and each case turned out to want
`--dont-search-in` or a migration nobody had done.
