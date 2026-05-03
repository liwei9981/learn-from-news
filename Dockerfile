FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Copy project specification
COPY pyproject.toml .

# Install dependencies
RUN pip install -e .

# Install Playwright dependencies (required for notebooklm-py)
RUN playwright install --with-deps chromium

# Copy the rest of the application code
COPY . .

# Ensure storage directories exist
RUN mkdir -p .local/notebooklm-storage "Output files"

# Default command to run the Telegram bot
CMD ["python3", "-m", "app.bot"]
