FROM python:3.11-slim

# Install system deps for httpx / xml / dateutil if needed
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    libxml2-dev libxslt1-dev ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000

# Use uvicorn with a single gunicorn worker using uvicorn worker in production,
# but here we run uvicorn directly (for simplicity). In k8s use gunicorn+uvicorn workers.
CMD ["uvicorn", "app.euraxess_mcp:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "uvloop", "--http", "h11"]
