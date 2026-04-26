#!/usr/bin/env python3

import json
from pathlib import Path
import sys


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def main() -> None:
    evidence = json.loads(
        Path("contracts/collector/FAILURE_SIMULATION_EVIDENCE.json").read_text(
            encoding="utf-8"
        )
    )
    simulations = evidence.get("simulations", [])
    if not simulations:
        fail("No simulations found in bounded-loss evidence.")

    for sim in simulations:
        name = sim.get("name", "unknown")
        observed = sim.get("observed", {})
        dropped = observed.get("dropped_items_total", 0)
        sent = observed.get("total_items_sent")
        if sent is None:
            if dropped < 0:
                fail(f"{name}: dropped_items_total must be non-negative.")
            continue
        if sent <= 0:
            fail(f"{name}: total_items_sent must be greater than zero.")
        loss_ratio = dropped / sent
        if loss_ratio > 0.0005:
            fail(f"{name}: bounded loss ratio exceeded threshold: {loss_ratio:.6f}")

    print("Bounded-loss simulation metrics validation passed.")


if __name__ == "__main__":
    main()
