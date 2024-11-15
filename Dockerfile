FROM python:3.10-slim

# Install necessary packages
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Create logs directory and files with proper permissions
RUN mkdir -p /var/log/m3u8proxy && \
    touch /var/log/m3u8proxy/access.log && \
    touch /var/log/m3u8proxy/error.log && \
    chown -R nobody:nogroup /var/log/m3u8proxy && \
    chmod -R 777 /var/log/m3u8proxy && \
    chmod 666 /var/log/m3u8proxy/access.log && \
    chmod 666 /var/log/m3u8proxy/error.log

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Switch to non-root user
USER nobody

# Run command
CMD gunicorn \
    --workers ${WORKERS:-4} \
    --timeout ${TIMEOUT:-300} \
    --max-requests ${MAX_REQUESTS:-1000} \
    --bind 0.0.0.0:5001 \
    --access-logfile /var/log/m3u8proxy/access.log \
    --error-logfile /var/log/m3u8proxy/error.log \
    main:app
