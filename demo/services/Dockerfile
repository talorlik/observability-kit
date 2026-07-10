# Demo playground image (Batch 27, ADR-0011): one image, five
# entrypoints (http-api, worker, scheduled-job, datastore, loadgen),
# selected by the container args - the services/ai image pattern.
# Built locally on the disposable harness and side-loaded with
# `kind load docker-image`; the demo is optional, additive, and
# removable, never a platform component.
#
# python:3.12-slim (glibc) matches the AI runtime base. The package
# is standard-library-only, so `pip install` resolves nothing from
# any index and the build is reproducible offline.
FROM python:3.12-slim

COPY pyproject.toml /src/
COPY demosvc /src/demosvc

RUN pip install --no-cache-dir "/src" && rm -rf /src

# Unbuffered stdout so structured log lines reach the pod log stream
# immediately.
ENV PYTHONUNBUFFERED=1

# Non-root (nobody), matching the restricted pod security posture of
# the tenant-demo namespace manifests.
USER 65534

ENTRYPOINT ["python3", "-m", "demosvc"]
