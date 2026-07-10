"""Offline end-to-end tests for the metering job (Batch 22 Task 2).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 22 validator - never under pytest. Drives the
full wiring the completion check names: source -> builder ->
validator -> sink for one UTC-day window, in --fixture mode, writing
schema-conformant records for all four dimensions to a
control-tenancy-usage-v1-* index, every record carrying tenant_id.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
FIXTURE = TESTS_DIR / "fixtures" / "aggregation_window_2026_07_09.json"

sys.path.insert(0, str(REPO_ROOT / "services" / "commercial"))

from commercialsvc.metering import main as metering_main  # noqa: E402
from commercialsvc.metering import run_job  # noqa: E402
from commercialsvc.models import DIMENSIONS  # noqa: E402
from commercialsvc.sinks import (  # noqa: E402
    InMemorySink,
    usage_index_for,
)
from commercialsvc.sources import FixtureSource  # noqa: E402
from commercialsvc.validation import validate_record  # noqa: E402

EXPECTED_INDEX = "control-tenancy-usage-v1-2026.07.09"


def test_end_to_end_fixture_run() -> None:
    source = FixtureSource(FIXTURE)
    window = source.fixture_window()
    sink = InMemorySink()
    records = run_job(source, sink, window)

    assert usage_index_for(window) == EXPECTED_INDEX
    documents = sink.written[EXPECTED_INDEX]
    assert len(documents) == len(records)
    # Every written document is schema-conformant and attributed.
    for document in documents:
        assert document["tenant_id"], "record without tenant_id"
        errors = validate_record(document)
        assert not errors, f"{document['record_id']}: {errors}"
    # All four contract dimensions landed in the control-plane index.
    assert {
        document["dimension"] for document in documents
    } == set(DIMENSIONS)


def test_job_is_idempotent_across_runs() -> None:
    source = FixtureSource(FIXTURE)
    window = source.fixture_window()
    first = run_job(
        source, InMemorySink(), window,
        collected_at="2026-07-10T01:05:00Z",
    )
    second = run_job(
        source, InMemorySink(), window,
        collected_at="2026-07-10T02:00:00Z",
    )
    assert [record.record_id for record in first] == [
        record.record_id for record in second
    ]
    for one, two in zip(first, second):
        left = one.to_dict()
        right = two.to_dict()
        del left["collected_at"]
        del right["collected_at"]
        assert left == right


def test_cli_fixture_mode_writes_output_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        exit_code = metering_main(
            [
                "--fixture",
                str(FIXTURE),
                "--output-dir",
                str(directory),
            ]
        )
        assert exit_code == 0
        output = directory / f"{EXPECTED_INDEX}.json"
        assert output.exists()
        documents = json.loads(output.read_text(encoding="utf-8"))
        assert documents
        for document in documents:
            assert document["tenant_id"]
            assert not validate_record(document)


def test_cli_dry_run_without_output_dir() -> None:
    # Fixture mode with no output dir routes through the in-memory
    # sink: a fully validated dry run.
    assert metering_main(["--fixture", str(FIXTURE)]) == 0


def test_cli_fails_loudly_on_bad_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.json"
        bad.write_text('{"window": {}}', encoding="utf-8")
        assert metering_main(["--fixture", str(bad)]) == 1


def main() -> int:
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]
    for name, func in tests:
        func()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
