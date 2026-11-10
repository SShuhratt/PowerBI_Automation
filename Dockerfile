FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root system user
RUN groupadd -r autobi && useradd -r -g autobi -d /app -s /sbin/nologin autobi

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure storage directories exist and have proper permissions
RUN mkdir -p /app/.sessions /app/output && chown -R autobi:autobi /app

# Switch to non-root user
USER autobi

# Expose web portal port
EXPOSE 5000

# Run via Gunicorn multi-worker WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--threads", "2", "--timeout", "120", "web_app:app"]
