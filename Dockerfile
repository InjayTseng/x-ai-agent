FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libglib2.0-0 \
    libnss3-tools \
    libxss1 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and browser
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps

# Copy application files
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAILWAY_ENVIRONMENT=production

# Set browser launch arguments
ENV BROWSER_ARGS="--disable-dev-shm-usage --no-sandbox --disable-setuid-sandbox --disable-gpu"

# Run the application
CMD ["python", "main.py"]
