"""Guided installer subpackage (Batch 18, TR-19; ADR-0002).

Composes the Batch 17 executor into the contracted install flow:
preflight, grading, mode recommendation, contract capture, render,
Argo CD bootstrap, post-install readiness. Entry point: the
`obskit install` subcommand (obskit.cli routes to obskit.install.flow).
"""
