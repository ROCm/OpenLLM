"""
This type stub file was generated by pyright.
"""

import sys

from IPython.core.magic import Magics
from IPython.core.magic import line_magic
from IPython.core.magic import magics_class
from IPython.testing.skipdoctest import skip_doctest

"""Extra magics for terminal use."""

def get_pasted_lines(sentinel, l_input=..., quiet=...):  # -> Generator[Unknown, Any, None]:
    """Yield pasted lines until the user enters the given sentinel value."""
    ...

@magics_class
class TerminalMagics(Magics):
    def __init__(self, shell) -> None: ...
    def store_or_execute(self, block, name, store_history=...):  # -> None:
        """Execute a block, or store it in a variable, per the user's request."""
        ...
    def preclean_input(self, block): ...
    def rerun_pasted(self, name=...):  # -> None:
        """Rerun a previously pasted command."""
        ...
    @line_magic
    def autoindent(self, parameter_s=...):  # -> None:
        """Toggle autoindent on/off (deprecated)"""
        ...
    @skip_doctest
    @line_magic
    def cpaste(self, parameter_s=...):  # -> None:
        """Paste & execute a pre-formatted code block from clipboard.

        You must terminate the block with '--' (two minus-signs) or Ctrl-D
        alone on the line. You can also provide your own sentinel with '%paste
        -s %%' ('%%' is the new sentinel for this operation).

        The block is dedented prior to execution to enable execution of method
        definitions. '>' and '+' characters at the beginning of a line are
        ignored, to allow pasting directly from e-mails, diff files and
        doctests (the '...' continuation prompt is also stripped).  The
        executed block is also assigned to variable named 'pasted_block' for
        later editing with '%edit pasted_block'.

        You can also pass a variable name as an argument, e.g. '%cpaste foo'.
        This assigns the pasted block to variable 'foo' as string, without
        dedenting or executing it (preceding >>> and + is still stripped)

        '%cpaste -r' re-executes the block previously entered by cpaste.
        '%cpaste -q' suppresses any additional output messages.

        Do not be alarmed by garbled output on Windows (it's a readline bug).
        Just press enter and type -- (and press enter again) and the block
        will be what was just pasted.

        Shell escapes are not supported (yet).

        See Also
        --------
        paste : automatically pull code from clipboard.

        Examples
        --------
        ::

          In [8]: %cpaste
          Pasting code; enter '--' alone on the line to stop.
          :>>> a = ["world!", "Hello"]
          :>>> print(" ".join(sorted(a)))
          :--
          Hello world!

        ::
          In [8]: %cpaste
          Pasting code; enter '--' alone on the line to stop.
          :>>> %alias_magic t timeit
          :>>> %t -n1 pass
          :--
          Created `%t` as an alias for `%timeit`.
          Created `%%t` as an alias for `%%timeit`.
          354 ns ± 224 ns per loop (mean ± std. dev. of 7 runs, 1 loop each)
        """
        ...
    @line_magic
    def paste(self, parameter_s=...):  # -> None:
        """Paste & execute a pre-formatted code block from clipboard.

        The text is pulled directly from the clipboard without user
        intervention and printed back on the screen before execution (unless
        the -q flag is given to force quiet mode).

        The block is dedented prior to execution to enable execution of method
        definitions. '>' and '+' characters at the beginning of a line are
        ignored, to allow pasting directly from e-mails, diff files and
        doctests (the '...' continuation prompt is also stripped).  The
        executed block is also assigned to variable named 'pasted_block' for
        later editing with '%edit pasted_block'.

        You can also pass a variable name as an argument, e.g. '%paste foo'.
        This assigns the pasted block to variable 'foo' as string, without
        executing it (preceding >>> and + is still stripped).

        Options:

          -r: re-executes the block previously entered by cpaste.

          -q: quiet mode: do not echo the pasted text back to the terminal.

        IPython statements (magics, shell escapes) are not supported (yet).

        See Also
        --------
        cpaste : manually paste code into terminal until you mark its end.
        """
        ...
    if sys.platform == "win32": ...