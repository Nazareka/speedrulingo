FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

# Dev image: install locked dependencies into the image and bind-mount source at runtime.
RUN uv export --frozen --no-dev --no-emit-project --format requirements.txt --output-file requirements.txt \
    && uv pip install --system -r requirements.txt \
    && rm requirements.txt

ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
