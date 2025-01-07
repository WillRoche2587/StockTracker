FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy application code
COPY app /app

# Install dependencies
RUN pip install fastapi uvicorn yfinance websockets aiofiles

# Expose port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]