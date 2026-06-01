FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
COPY models ./models

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data

CMD ["uvicorn", "elevator_pdm.presentation.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
