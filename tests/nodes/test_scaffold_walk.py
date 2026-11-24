from dataclasses import dataclass, field

from fakes import ROOT, FakeFs

from ambler.nodes.scaffold_walk import Outcome, ScaffoldWalk

WALK_FILE = ROOT / "src" / "demo" / "walks" / "counter.py"
TEST_FILE = ROOT / "tests" / "walks" / "test_counter.py"
SPEC_FILE = ROOT / "specs" / "counter.md"

ARGV = [
    "counter",
    "--nodes",
    "count,stop",
    "--edge",
    "count.again=count",
    "--edge",
    "count.finished=stop",
]


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    exit_code: int = 0


async def test_writes_walk_test_and_spec() -> None:
    fs = FakeFs()
    state = MockState(argv=ARGV)
    assert await ScaffoldWalk(fs).run(state) == Outcome.DONE

    walk = fs.files[WALK_FILE]
    assert "class Counter(Walk[Id, State]):" in walk
    assert "case Count.Outcome.AGAIN:" in walk
    assert "return Id.STOP" in walk
    assert "# Wire outcomes for stop" in walk
    assert "Id.COUNT, State()" in walk
    assert "Initial node: `count`." in fs.files[SPEC_FILE]
    assert "count -> stop" in fs.files[SPEC_FILE]
    assert "Id.COUNT" in fs.files[TEST_FILE]
    assert fs.out == [
        f"Created {WALK_FILE}",
        f"Created {TEST_FILE}",
        f"Created {SPEC_FILE}",
    ]
    assert state.exit_code == 0


async def test_halt_target_returns_none_and_bad_edges_are_ignored() -> None:
    fs = FakeFs()
    argv = ["w", "--nodes", "a", "--edge", "a.done=halt", "--edge", "nonsense"]
    await ScaffoldWalk(fs).run(MockState(argv=argv))
    walk = fs.files[ROOT / "src" / "demo" / "walks" / "w.py"]
    assert "case A.Outcome.DONE:\n                        return None" in walk


async def test_keeps_an_existing_spec() -> None:
    fs = FakeFs({SPEC_FILE: "mine"})
    await ScaffoldWalk(fs).run(MockState(argv=ARGV))
    assert fs.files[SPEC_FILE] == "mine"


async def test_existing_walk_fails_with_exit_code_1() -> None:
    fs = FakeFs({WALK_FILE: "old"})
    state = MockState(argv=ARGV)
    assert await ScaffoldWalk(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 1
    assert fs.files == {WALK_FILE: "old"}


async def test_missing_nodes_option_fails_with_exit_code_2() -> None:
    fs = FakeFs()
    state = MockState(argv=["counter"])
    assert await ScaffoldWalk(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 2


async def test_empty_nodes_fail_with_exit_code_2() -> None:
    fs = FakeFs()
    state = MockState(argv=["counter", "--nodes", ","])
    assert await ScaffoldWalk(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 2
    assert fs.errors == ["Error: --nodes must contain at least one node name"]


async def test_no_runner_is_accepted() -> None:
    fs = FakeFs()
    state = MockState(argv=[*ARGV, "--no-runner"])
    assert await ScaffoldWalk(fs).run(state) == Outcome.DONE
