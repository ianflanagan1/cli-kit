"""The foundation of my command line tools.

cli: a command line of subcommands, with help, status lines and exit statuses.
outcome: how a command ends, Done or NothingToDo, and the changes it made on the way.
errors: Precondition and Failure, the problems a command raises for the user to fix.
proc: running other programs, such as git and gh.
credentials: tokens from the system credential store.
terminal: asking the person at the terminal.
colour: colour on a terminal, honouring NO_COLOR and FORCE_COLOR.
devbox: putting the tool's devbox packages on the PATH.
"""
