#!/usr/bin/env python3

"""Backtesting helpers for deterministic risk scoring evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int


def precision(matrix: ConfusionMatrix) -> float:
    denom = matrix.true_positive + matrix.false_positive
    return 0.0 if denom == 0 else matrix.true_positive / denom


def recall(matrix: ConfusionMatrix) -> float:
    denom = matrix.true_positive + matrix.false_negative
    return 0.0 if denom == 0 else matrix.true_positive / denom


def f1_score(matrix: ConfusionMatrix) -> float:
    p = precision(matrix)
    r = recall(matrix)
    denom = p + r
    return 0.0 if denom == 0 else (2 * p * r) / denom
