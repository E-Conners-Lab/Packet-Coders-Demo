# Packet Coders MCP server + mcpo (OpenAPI tool server) in one small image.
FROM python:3.11-slim

# uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs

# Install the lab server (editable, so a mounted ./src mirrors what you read in your IDE)
# plus mcpo, which wraps the stdio MCP server as an OpenAPI tool server.
RUN uv pip install --system -e . mcpo

# Mock lab by default — no hardware needed. Override via compose for a real lab.
ENV PACKET_CODERS_INVENTORY=/app/configs/inventory.mock.yaml

EXPOSE 8000
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--", "packet-coders-mcp"]
