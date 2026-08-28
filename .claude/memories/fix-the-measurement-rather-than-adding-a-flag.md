# Fix the measurement rather than adding a flag

Do not add a flag so the caller can work around a bad answer. Make the
answer better and the flag has nothing left to decide.
`--count-defining-file` existed because searching a file's text cannot tell
a call from a docstring. Parsing the file tells them apart, so the flag was
deleted.
