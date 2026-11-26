# CLI Specification

The native Ambler Tooling Protocol (ATP) command-line tool, run as `uv run ambler <command> [options]` (`ambler-cli` is kept as an alias). It scaffolds nodes, walks and utils, and runs the project checks. `ambler.cli.main` is a thin shim that runs this walk and exits with the final `exit_code`.

## Nodes

### CliRoute
- Initial node of the application.
- Takes the first entry of `argv` as the command and removes it from `argv`.
- `node` transitions to `SCAFFOLD_NODE`, `walk` to `SCAFFOLD_WALK`, `util` to `SCAFFOLD_UTIL`, `check` to `RUN_CHECKS`.
- `help`, `--help` or `-h` transitions to `CLI_HELP` (exit code 0), leaving any topic in `argv`.
- No command transitions to `CLI_HELP` with exit code 2.
- Any other command transitions to `CLI_ERROR`.

### ScaffoldNode
- Usage: `node <name> (--outcomes <a,b> | --terminal) [--fallible] [--state <name:type>...]`.
- Writes `src/<pkg>/nodes/<name>.py` and `tests/nodes/test_<name>.py`, and adds a `Has<Field>` protocol to `src/<pkg>/nodes/__init__.py` for each state field that lacks one.
- Missing name, missing `--outcomes`/`--terminal`, or no `pyproject.toml`: prints an error, exit code 2 (1 without a project), halts.
- Node already exists: prints an error, exit code 1, halts.
- Otherwise prints the created paths and halts.

### ScaffoldWalk
- Usage: `walk <name> --nodes <n1,n2> [--edge <node.OUTCOME=target>...] [--no-runner]`. Edges may also be separated by commas; outcomes may be given in any case; `halt` as the target ends the walk.
- Reads each node from `src/<pkg>/nodes/<node>.py`: its `Outcome` members (none if `run` returns `None`), whether it has an `Error`, the `Has*` protocols its `run` takes (directly or through a local `State` protocol) and its `Utils` methods; and the fields of those protocols from `src/<pkg>/nodes/__init__.py`.
- Writes `src/<pkg>/walks/<name>.py` as `uv run ambler help walk` describes: `__all__`, `Error` if any node can fail (a tuple if several can), a `State` dataclass with every field the nodes need and a default for each, `Id`, the walk class whose `step` matches every outcome (outcomes without an edge raise `not yet wired: NODE.OUTCOME`), `run()` and `main()`. Writes `tests/walks/test_<name>.py` with a `Script` that stands in for every node's utils and one unfinished test, and `specs/<name>.md` with a section per node if it does not exist. Unless `--no-runner`, adds a `<name>` script running the walk's `main` to `[project.scripts]` in `pyproject.toml`.
- Missing name, missing or empty `--nodes`, a malformed edge, an edge naming an unknown node, outcome or target, an edge from a terminal node, a node that cannot be read, or two nodes giving a field different types: exit code 2. A missing node: exit code 2, listing the `node` commands to run first. No `pyproject.toml`: exit code 1. Walk or script already exists: exit code 1. Nothing is written when it fails.
- Otherwise prints the created paths and what to do next, and halts.

### ScaffoldUtil
- Usage: `util <name>`.
- Writes `src/<pkg>/utils/<name>.py`.
- Missing name: exit code 2. No `pyproject.toml`: exit code 1. Util already exists: exit code 1.
- Otherwise prints the created path and halts.

### RunChecks
- Usage: `check [--lint-only]`.
- First checks the conventions of the project's nodes, walks and utilities (`src/<pkg>/nodes`, `walks`, `utils`) and its tests (`tests/`), printing one line per violation as `<path>:<line>: <rule>: <what to do>`. The one rule so far is `todo`: no placeholder the scaffolders write is left, that is no `raise NotImplementedError("not yet implemented")` and no `raise NotImplementedError("not yet wired: …")`. A file that does not parse is left to the tools. If there are violations, it prints how many, sets exit code 1 and halts, with or without `--lint-only`.
- Then runs `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` and, unless `--lint-only`, `uv run pytest`, stopping at the first failure. A `pytest` exit code of 5 (no tests collected) is not a failure.
- On failure prints the failed step, sets the exit code to the step's exit code and halts.
- If all pass, prints a success message and halts.

### CliHelp
- Usage: `help [topic]`.
- For `help`, prints the guide for the topic in `argv`, or the general guide if there is none, and halts. An unknown topic prints the known topics on standard error, sets exit code 1 and halts.
- For `--help`, `-h` or no command, prints the usage text and halts, keeping the exit code.

### CliError
- Prints `Unknown command: <command>`, sets exit code 2 and halts.

## Shared State

The shared state consists of:
- `argv`: the command-line arguments; the command is consumed by `CliRoute`, leaving the options for the handler.
- `command`: the command name consumed by `CliRoute` (used for the unknown-command message).
- `exit_code`: the process exit code (starts at 0).
