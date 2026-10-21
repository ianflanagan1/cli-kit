"""The foundation of my command line tools.

cli: a command line of subcommands, with help, status lines and exit statuses.
outcome: how a command ends: it returns Done or NothingToDo, or raises Precondition or Failure,
    and records each change it makes on the way.
proc: running other programs, such as git and gh.
credentials: tokens from the system credential store.
terminal: asking the person at the terminal.
colour: colour on a terminal, honouring NO_COLOR and FORCE_COLOR.
devbox: putting the tool's devbox packages on the PATH.
link: linking a tool's commands onto your PATH, which each tool's setup runs.
"""
