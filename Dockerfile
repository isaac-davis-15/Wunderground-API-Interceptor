# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the logger script into the image
COPY weatherstation_logger.py .

# Make sure it’s executable
RUN chmod +x weatherstation_logger.py

# Expose the default listening port
EXPOSE 80

# Allow override of port at runtime
ENV PORT=80

# ensure print() goes straight to stdout without buffering
ENV PYTHONUNBUFFERED=1

# install prometheus_client
RUN pip install --no-cache-dir prometheus_client

# Run the script, passing in the port from the env var
CMD ["sh", "-c", "exec ./weatherstation_logger.py --port ${PORT}"]
