FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 (레이어 캐시)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir ".[api]"

COPY coinforge ./coinforge
COPY scripts ./scripts

# 기본: paper 트레이더. compose 에서 command 로 override.
CMD ["python", "-m", "coinforge.cli.trader"]
