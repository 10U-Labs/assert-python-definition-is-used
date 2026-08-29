# jscpd reads a docstring as ordinary tokens

A docstring is not one token to jscpd, so two functions whose bodies differ
but whose `Returns:` blocks match can clone on the docstring alone. Two
`run_over` fixtures written that way came to 8 lines and 63 tokens and
failed `jscpd (test)`.

Do not reword the docstring to duck it. Move the shared body into a plain
helper module both conftests call, so the only repetition left is the
fixture wrapper.
