FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Create startup script
RUN echo '#!/bin/bash\nuvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}' > /start.sh && chmod +x /start.sh

# Start command
CMD ["/bin/bash", "/start.sh"]
