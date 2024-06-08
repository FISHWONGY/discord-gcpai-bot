FROM python:3.10-slim

WORKDIR /usr/src/app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.3.0

RUN apt-get update && apt-get install -y curl
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.3.0 python3 -
ENV PATH="/root/.local/bin:$PATH"
COPY ./poetry.lock pyproject.toml /usr/src/app/
RUN poetry install -nv --no-root

COPY creds creds
COPY app .
CMD ["poetry", "run", "python3", "main.py"]
