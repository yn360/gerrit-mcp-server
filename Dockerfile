FROM python:3.12-alpine AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY gerrit_mcp_server/ gerrit_mcp_server/

RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-alpine

# curl: required to call the Gerrit REST API.
# Non-root system user matching the Helm chart (runAsUser: 1000).
RUN apk add --no-cache curl \
 && addgroup -S -g 1000 mcp \
 && adduser  -S -u 1000 -G mcp mcp

COPY --from=builder /install /usr/local

# gerrit_config.json will be mounted here by the Helm chart (K8s Secret).
ENV GERRIT_CONFIG_PATH=/config/gerrit_config.json

# Write logs to /tmp (emptyDir, writable) instead of the read-only app dir.
# The Helm chart sets readOnlyRootFilesystem: true, so /app is not writable.
ENV GERRIT_LOG_FILE=/tmp/server.log

# Use /tmp as working directory — it is an in-memory emptyDir in K8s and is
# writable even with readOnlyRootFilesystem: true.
WORKDIR /tmp

USER mcp

EXPOSE 6322

CMD ["uvicorn", "gerrit_mcp_server.main:app", \
     "--host", "0.0.0.0", \
     "--port", "6322"]
