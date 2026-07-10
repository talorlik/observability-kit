"""KHook trigger dispatcher: read-only Kubernetes event polling with
dedupe and burst control, dispatching khook_to_kagent envelopes.

The poll loop is deliberately thin: all matching, normalization,
enrichment, dedupe, and burst logic lives in pure functions and the
EventProcessor state machine, both driven with plain event dicts and a
caller-supplied clock so the offline tests exercise the exact contract
rules without a cluster.
"""

from __future__ import annotations

import hashlib
import json
import ssl
import threading
import time
import urllib.request
from typing import Any

from airuntime.contracts import (
    BURST_MAX_PER_WINDOW,
    BURST_WINDOW_SECONDS,
    CORRELATION_KEY_FIELDS,
    DEDUPE_KEY_FIELDS,
    DEDUPE_WINDOW_SECONDS,
    EDGE_VERSION,
    HOOKS,
    REQUIRED_EVENT_FIELDS,
)
from airuntime.httpd import JsonApi, http_json, serve

_SA_ROOT = "/var/run/secrets/kubernetes.io/serviceaccount"
DEFAULT_KAGENT_URL = (
    "http://kagent-controller.ai-runtime.svc.cluster.local:8080"
)


def match_hook(raw_event: dict[str, Any]) -> str | None:
    """Match a raw k8s Event against the hook catalog by
    (involvedObject.kind, reason)."""
    kind = raw_event.get("involvedObject", {}).get("kind")
    reason = raw_event.get("reason")
    for hook_id, (hook_kind, hook_reason, _severity) in HOOKS.items():
        if kind == hook_kind and reason == hook_reason:
            return hook_id
    return None


def normalize_event(
    raw_event: dict[str, Any], cluster: str
) -> dict[str, Any]:
    """Project a raw k8s Event onto REQUIRED_EVENT_FIELDS."""
    metadata = raw_event.get("metadata", {})
    involved = raw_event.get("involvedObject", {})
    event_id = metadata.get("uid")
    if not event_id:
        raise ValueError("k8s Event without metadata.uid cannot be tracked")
    normalized = {
        "event_id": event_id,
        "event_timestamp": (
            raw_event.get("lastTimestamp")
            or raw_event.get("eventTime")
            or metadata.get("creationTimestamp")
        ),
        "cluster": cluster,
        "namespace": involved.get("namespace")
        or metadata.get("namespace")
        or "",
        "object_kind": involved.get("kind"),
        "object_name": involved.get("name"),
        "reason": raw_event.get("reason"),
        "message": raw_event.get("message", ""),
    }
    missing = [f for f in REQUIRED_EVENT_FIELDS if normalized.get(f) is None]
    if missing:
        raise ValueError(f"normalized event missing fields: {missing}")
    return normalized


def correlation_key(normalized: dict[str, Any]) -> str:
    """Stable sha256 over the enrichment contract's five fields."""
    material = "|".join(
        str(normalized[field]) for field in CORRELATION_KEY_FIELDS
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _dedupe_key(enriched: dict[str, Any]) -> str:
    return "|".join(str(enriched[field]) for field in DEDUPE_KEY_FIELDS)


def build_dispatch(
    enriched: dict[str, Any],
    hook_id: str,
    burst_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """khook_to_kagent envelope. Dispatch is read-only, hence the fixed
    read.safe risk class regardless of hook severity."""
    payload = dict(enriched)
    payload["severity"] = HOOKS[hook_id][2]
    if burst_info is not None:
        payload.update(burst_info)
        payload["burst"] = True
    return {
        "edge_version": EDGE_VERSION,
        "correlation_id": enriched["incident_correlation_key"],
        "event_type": hook_id,
        "source_namespace": enriched["namespace"],
        "risk_class": "read.safe",
        "payload": payload,
    }


class EventProcessor:
    """Dedupe/burst state machine over normalized events.

    In-memory state IS the dedupe store per the contract's resilience
    posture: an internal error means fail closed (no dispatch), and a
    restart re-arms dedupe from empty, which at worst re-dispatches one
    event per key - the controller dedupes again by correlation id.
    """

    def __init__(self, cluster: str) -> None:
        self.cluster = cluster
        self._seen_uids: set[str] = set()
        self._last_dispatch_ts: dict[str, float] = {}
        # key -> [(clock_ts, event_timestamp), ...] within the burst window
        self._window: dict[str, list[tuple[float, str]]] = {}
        self._burst_emitted_ts: dict[str, float] = {}
        self.counters: dict[str, int] = {
            "polled": 0,
            "matched": 0,
            "ignored": 0,
            "duplicate_uid": 0,
            "dispatched": 0,
            "deduped": 0,
            "burst_summaries": 0,
            "burst_suppressed": 0,
            "dispatch_failures": 0,
        }

    def process(
        self, raw_event: dict[str, Any], now_ts: float
    ) -> dict[str, Any] | None:
        """Returns a dispatch envelope, or None when suppressed/ignored."""
        self.counters["polled"] += 1
        uid = raw_event.get("metadata", {}).get("uid")
        if not uid:
            raise ValueError("event without metadata.uid")
        if uid in self._seen_uids:
            # The list API returns the same Event objects every poll;
            # each object dispatches at most once.
            self.counters["duplicate_uid"] += 1
            return None
        self._seen_uids.add(uid)
        hook_id = match_hook(raw_event)
        if hook_id is None:
            self.counters["ignored"] += 1
            return None
        self.counters["matched"] += 1
        enriched = normalize_event(raw_event, self.cluster)
        enriched["incident_correlation_key"] = correlation_key(enriched)
        key = _dedupe_key(enriched)

        window = self._window.setdefault(key, [])
        window[:] = [
            entry
            for entry in window
            if entry[0] > now_ts - BURST_WINDOW_SECONDS
        ]
        window.append((now_ts, enriched["event_timestamp"]))

        if len(window) > BURST_MAX_PER_WINDOW:
            last_burst = self._burst_emitted_ts.get(key)
            if (
                last_burst is not None
                and now_ts - last_burst < BURST_WINDOW_SECONDS
            ):
                # One summary per burst window; the rest stay silent.
                self.counters["burst_suppressed"] += 1
                return None
            self._burst_emitted_ts[key] = now_ts
            self._last_dispatch_ts[key] = now_ts
            self.counters["burst_summaries"] += 1
            return build_dispatch(
                enriched,
                hook_id,
                burst_info={
                    # All window events except the one that dispatched
                    # individually were suppressed into this summary.
                    "suppressed_event_count": len(window) - 1,
                    "first_seen_at": window[0][1],
                    "last_seen_at": window[-1][1],
                },
            )

        last = self._last_dispatch_ts.get(key)
        if last is not None and now_ts - last < DEDUPE_WINDOW_SECONDS:
            self.counters["deduped"] += 1
            return None
        self._last_dispatch_ts[key] = now_ts
        self.counters["dispatched"] += 1
        return build_dispatch(enriched, hook_id)


def fetch_events(env: dict[str, str]) -> list[dict[str, Any]]:
    """Read-only in-cluster event list via the serviceaccount identity."""
    with open(f"{_SA_ROOT}/token", encoding="utf-8") as fh:
        token = fh.read().strip()
    context = ssl.create_default_context(cafile=f"{_SA_ROOT}/ca.crt")
    host = env["KUBERNETES_SERVICE_HOST"]
    port = env.get("KUBERNETES_SERVICE_PORT", "443")
    namespaces = [
        ns for ns in env.get("WATCH_NAMESPACES", "").split(",") if ns
    ]
    urls = (
        [
            f"https://{host}:{port}/api/v1/namespaces/{ns}/events"
            for ns in namespaces
        ]
        if namespaces
        else [f"https://{host}:{port}/api/v1/events"]
    )
    items: list[dict[str, Any]] = []
    for url in urls:
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(
            request, timeout=10, context=context
        ) as response:
            items.extend(json.loads(response.read()).get("items", []))
    return items


def run(env: dict[str, str]) -> int:
    kagent_url = env.get("KAGENT_URL", DEFAULT_KAGENT_URL)
    cluster = env.get("CLUSTER_NAME", "harness")
    poll_interval = float(env.get("POLL_INTERVAL_SECONDS", "5"))
    port = int(env.get("KHOOK_PORT", "8090"))
    processor = EventProcessor(cluster)

    api = JsonApi("khook")

    def state(
        _subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        return 200, {"component": "khook", "counters": dict(processor.counters)}

    api.route("GET", "/state", state)
    threading.Thread(target=serve, args=(api, port), daemon=True).start()

    while True:
        try:
            raw_events = fetch_events(env)
        except Exception as exc:
            print(f"[khook] event poll failed: {exc}")
            time.sleep(poll_interval)
            continue
        now_ts = time.monotonic()
        for raw_event in raw_events:
            try:
                envelope = processor.process(raw_event, now_ts)
            except Exception as exc:
                # Fail closed: an internal processing error must not
                # produce a dispatch.
                print(f"[khook] event processing failed, not dispatching: {exc}")
                continue
            if envelope is None:
                continue
            try:
                status, _payload = http_json(
                    "POST", f"{kagent_url}/triggers", envelope
                )
                if status >= 400:
                    raise RuntimeError(f"kagent returned {status}")
            except Exception as exc:
                # Controller unreachable: log and retry next poll.
                processor.counters["dispatch_failures"] += 1
                print(f"[khook] dispatch failed: {exc}")
        time.sleep(poll_interval)
