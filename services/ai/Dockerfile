# AI runtime image (Batch 24, ADR-0009): one image, four entrypoints
# (kagent, khook, gateway, mcpserver), selected by the container args.
# Built locally on the disposable harness and side-loaded with
# `kind load docker-image`; registry publication is Batch 25 release
# engineering scope.
#
# python:3.12-slim (glibc) keeps the pg8000 pure-Python driver and
# the stdlib-only runtime free of platform-specific wheels.

FROM python:3.12-slim

# The runtime executes contract constants embedded in the package; no
# YAML parser, no vendor SDK, no datastore client beyond the
# contracted persistence driver.
COPY pyproject.toml /src/
COPY airuntime /src/airuntime
RUN pip install --no-cache-dir "/src[postgres]" && rm -rf /src

# Unbuffered stdout so audit journal lines reach the pod log stream
# immediately (the gateway journal doubles as log evidence).
ENV PYTHONUNBUFFERED=1

# Non-root: the pod security posture of gitops/platform/ai applies.
USER 65534

ENTRYPOINT ["python3", "-m", "airuntime"]
