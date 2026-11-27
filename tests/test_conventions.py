from ambler.utils.conventions import state_protocols, todo

NOT_IMPLEMENTED = "not yet " + "implemented"
NOT_WIRED = "not yet " + "wired"


def test_finds_a_body_left_to_implement() -> None:
    source = (
        "async def run(self, state: object) -> None:\n"
        f'    raise NotImplementedError("{NOT_IMPLEMENTED}")\n'
    )

    assert todo("src/app/nodes/greet.py", source) == [
        "src/app/nodes/greet.py:2: todo: implement this: "
        f"it still raises `{NOT_IMPLEMENTED}`"
    ]


def test_finds_an_outcome_left_to_wire() -> None:
    source = (
        "match outcome:\n"
        "    case greet.Outcome.DONE:\n"
        f'        raise NotImplementedError("{NOT_WIRED}: GREET.DONE")\n'
    )

    assert todo("src/app/walks/hello.py", source) == [
        "src/app/walks/hello.py:3: todo: wire GREET.DONE: "
        "return the next `Id`, or `None` to end the walk"
    ]


def test_finds_every_placeholder_in_a_file() -> None:
    raise_it = f'    raise NotImplementedError("{NOT_IMPLEMENTED}")\n'
    source = f"def a() -> None:\n{raise_it}\n\ndef b() -> None:\n{raise_it}"

    assert [line.split(": ")[0] for line in todo("t.py", source)] == [
        "t.py:2",
        "t.py:6",
    ]


def test_ignores_mentions_that_are_not_placeholders() -> None:
    source = (
        f'MARKER = "{NOT_IMPLEMENTED}"\n'
        f'assert "{NOT_WIRED}: X.Y" in text\n'
        'raise NotImplementedError("something else")\n'
        f'raise ValueError("{NOT_IMPLEMENTED}")\n'
        "raise NotImplementedError\n"
    )

    assert todo("t.py", source) == []


def test_leaves_a_file_that_does_not_parse_to_the_tools() -> None:
    assert todo("t.py", "def broken(:\n") == []


REGISTRY = "src/app/nodes/__init__.py"
NODE = "src/app/nodes/greet.py"
HEADER = "from typing import Protocol\n\n\n"


def _rules(lines: list[str]) -> list[str]:
    """Each violation as ``<line>: <rule>``."""
    return [": ".join(line.split(": ")[0:2]).split(":", 1)[1] for line in lines]


def test_state_protocols_passes_the_convention() -> None:
    registry = HEADER + (
        "class HasName(Protocol):\n"
        '    """A state that has a name field."""\n\n'
        "    name: str\n\n\n"
        "class HasExitCode(Protocol):\n    exit_code: int\n"
    )
    node = (
        "from typing import Protocol\n\n"
        "from app.nodes import HasExitCode, HasName\n\n\n"
        "class State(HasName, HasExitCode, Protocol):\n    pass\n\n\n"
        "class Greet:\n"
        "    async def run(self, state: State) -> None:\n        pass\n"
    )
    single = (
        "from app.nodes import HasName\n\n\n"
        "class Greet:\n"
        "    async def run(self, state: HasName) -> None:\n        pass\n"
    )

    assert state_protocols(REGISTRY, registry) == []
    assert state_protocols(NODE, node) == []
    assert state_protocols("src/app/nodes/hi.py", single) == []
    assert state_protocols("src/app/walks/hello.py", "class State:\n    x: int\n") == []


def test_state_protocols_rejects_a_contract_with_two_fields() -> None:
    registry = HEADER + "class HasName(Protocol):\n    name: str\n    age: int\n"

    assert state_protocols(REGISTRY, registry) == [
        f"{REGISTRY}:4: state-protocols: `HasName` has 2 fields (`name`, `age`): "
        "give each field its own `Has<Field>` protocol"
    ]


def test_state_protocols_rejects_a_contract_with_no_field_or_a_method() -> None:
    registry = HEADER + ("class HasName(Protocol):\n    def name(self) -> str: ...\n")

    assert _rules(state_protocols(REGISTRY, registry)) == [
        "4: state-protocols",
        "5: state-protocols",
    ]


def test_state_protocols_rejects_a_contract_named_after_another_field() -> None:
    registry = HEADER + "class HasName(Protocol):\n    full_name: str\n"

    assert state_protocols(REGISTRY, registry) == [
        f"{REGISTRY}:4: state-protocols: `HasName` holds `full_name`: "
        "name it `HasFullName`"
    ]


def test_state_protocols_rejects_a_contract_extending_another() -> None:
    registry = HEADER + (
        "class HasName(Protocol):\n    name: str\n\n\n"
        "class HasAge(HasName, Protocol):\n    age: int\n"
    )

    assert _rules(state_protocols(REGISTRY, registry)) == ["8: state-protocols"]


def test_state_protocols_rejects_a_contract_outside_the_registry() -> None:
    source = HEADER + "class HasName(Protocol):\n    name: str\n"

    for path in (NODE, "src/app/walks/hello.py", "tests/nodes/test_greet.py"):
        assert state_protocols(path, source) == [
            f"{path}:4: state-protocols: `HasName` is a state contract: declare "
            "it in `nodes/__init__.py`, the only place `Has*` protocols live"
        ]


def test_state_protocols_rejects_a_field_on_a_local_state() -> None:
    node = (
        "from typing import Protocol\n\n"
        "from app.nodes import HasName\n\n\n"
        "class State(HasName, Protocol):\n    greeting: str\n"
    )

    assert state_protocols(NODE, node) == [
        f"{NODE}:7: state-protocols: `State` declares `greeting`: declare the "
        "field as a `Has<Field>` protocol in `nodes/__init__.py` and extend it"
    ]


def test_state_protocols_rejects_a_local_state_with_other_bases() -> None:
    node = (
        "from typing import Protocol\n\n"
        "from app.nodes import HasName\n"
        "from app.other import Named\n\n\n"
        "class Ctx(HasName, Named, Protocol):\n    pass\n\n\n"
        "class Greet:\n"
        "    async def run(self, state: Ctx) -> None:\n        pass\n"
    )

    assert state_protocols(NODE, node) == [
        f"{NODE}:7: state-protocols: `Ctx` extends `Named`: a node's state "
        "extends only `Has*` protocols and `Protocol`"
    ]


def test_state_protocols_leaves_a_file_that_does_not_parse_to_the_tools() -> None:
    assert state_protocols(REGISTRY, "class HasName(:\n") == []
