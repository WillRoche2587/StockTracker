# Use Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy application code into the container
COPY app /app

# Install dependencies
RUN pip install fastapi uvicorn yfinance websockets

# Expose port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
