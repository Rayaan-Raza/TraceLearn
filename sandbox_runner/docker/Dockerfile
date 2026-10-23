# TraceLearn sandbox image (Master Plan §9.2-U0, gate G0b).
#
# Build:   docker build -f sandbox_runner/docker/Dockerfile -t tracelearn-sandbox:0.2.0 .
# Pin:     python scripts/sandbox_manifest.py --image tracelearn-sandbox:0.2.0
#          (records the image id/digest; bulk runs then use image@sha256:...)
#
# Pin the base by digest before the bulk run. Resolve it once with
#   docker pull ubuntu:24.04 && docker inspect --format '{{index .RepoDigests 0}}' ubuntu:24.04
# and pass it as --build-arg BASE=ubuntu@sha256:<digest>.
ARG BASE=ubuntu:24.04
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ gcc clang valgrind python3 util-linux \
 && rm -rf /var/lib/apt/lists/*

COPY sandbox_runner /opt/sandbox/sandbox_runner
ENV PYTHONPATH=/opt/sandbox SANDBOX_PCH_DIR=/tmp/pch
WORKDIR /tmp
USER 65534:65534
ENTRYPOINT []
CMD ["python3", "-m", "sandbox_runner.cli", "env"]
