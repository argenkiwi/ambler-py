from ambler.utils.conventions import todo

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
