FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies if needed (e.g. git for private pip installs)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Try to install aristotle-mcp, but don't fail if it's private
RUN pip install "aristotle-mcp @ git+https://github.com/septract/lean-aristotle-mcp.git" || echo "Optional aristotlelib not installed"

COPY . ./

# Ensure data directory exists
RUN mkdir -p data

EXPOSE 8080

# Use a shell form for variable expansion
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
