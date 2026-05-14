FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_FETCH_MCP_CONFIG=/app/config.example.yaml \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config.example.yaml ./

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

EXPOSE 8000

CMD ["obscura-web-fetch-mcp"]
