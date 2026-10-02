FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --create-home --uid 10001 workbench && mkdir -p /data/artifacts && chown -R workbench:workbench /app /data
USER workbench
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
