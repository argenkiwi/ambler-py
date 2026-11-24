# CLI Specification

The native Ambler Tooling Protocol (ATP) command-line tool, run as `uv run ambler <command> [options]` (`ambler-cli` is kept as an alias). It scaffolds nodes, walks and utils, and runs the project checks. `ambler.cli.main` is a thin shim that runs this walk and exits with the final `exit_code`.

## Nodes

### CliRoute
- Initial node of the application.
- Takes the first entry of `argv` as the command and removes it from `argv`.
- `node` transitions to `SCAFFOLD_NODE`, `walk` to `SCAFFOLD_WALK`, `util` to `SCAFFOLD_UTIL`, `check` to `RUN_CHECKS`.
- `--help` or `-h` transitions to `CLI_HELP` (exit code 0).
- No command transitions to `CLI_HELP` with exit code 2.
- Any other command transitions to `CLI_ERROR`.

### ScaffoldNode
- Usage: `node <name> (--outcomes <a,b> | --terminal) [--fallible] [--state <name:type>...]`.
- Writes `src/<pkg>/nodes/<name>.py` and `tests/nodes/test_<name>.py`, and adds a `Has<Field>` protocol to `src/<pkg>/nodes/__init__.py` for each state field that lacks one.
- Missing name, missing `--outcomes`/`--terminal`, or no `pyproject.toml`: prints an error, exit code 2 (1 without a project), halts.
- Node already exists: prints an error, exit code 1, halts.
- Otherwise prints the created paths and halts.

### ScaffoldWalk
- Usage: `walk <name> --nodes <n1,n2> [--edge <node.OUTCOME=target>...] [--no-runner]`.
- Writes `src/<pkg>/walks/<name>.py` and `tests/walks/test_<name>.py`, plus `specs/<name>.md` if it does not exist. The first node is the start node. `--no-runner` is accepted but currently has no effect.
- Missing name, missing or empty `--nodes`: exit code 2. No `pyproject.toml`: exit code 1. Walk already exists: exit code 1.
- Otherwise prints the created paths and halts.

### ScaffoldUtil
- Usage: `util <name>`.
- Writes `src/<pkg>/utils/<name>.py`.
- Missing name: exit code 2. No `pyproject.toml`: exit code 1. Util already exists: exit code 1.
- Otherwise prints the created path and halts.

### RunChecks
- Usage: `check [--lint-only]`.
- Runs `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` and, unless `--lint-only`, `uv run pytest`, stopping at the first failure. A `pytest` exit code of 5 (no tests collected) is not a failure.
- On failure prints the failed step, sets the exit code to the step's exit code and halts.
- If all pass, prints a success message and halts.

### CliHelp
- Prints the usage text and halts.

### CliError
- Prints `Unknown command: <command>`, sets exit code 2 and halts.

## Shared State

The shared state consists of:
- `argv`: the command-line arguments; the command is consumed by `CliRoute`, leaving the options for the handler.
- `command`: the command name consumed by `CliRoute` (used for the unknown-command message).
- `exit_code`: the process exit code (starts at 0).
