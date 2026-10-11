FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Ensure unbuffered logs and no bytecode caching
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV LLM_MODE=offline

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and static assets
COPY src/ ./src/
COPY config/ ./config/
COPY static/ ./static/
COPY prompts/ ./prompts/

# Create non-root user for bank-grade security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose service port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:' + str(__import__('os').environ.get('PORT', 8000)) + '/healthz')" || exit 1

# Start FastAPI gateway via Uvicorn
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
