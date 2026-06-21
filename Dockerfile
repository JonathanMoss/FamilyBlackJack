# Base image using the stable Python 3.10 slim variant for a compact image size
FROM python:3.10-slim

# Set system environment variables to prevent Python from writing pyc files or buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establish our working directory inside the container
WORKDIR /app

# Install system dependencies needed for compiling gevent components
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements first to maximize Docker build caching speed
COPY requirements.txt /app/

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files into the container workspace
COPY . /app/

# Run the script to generate a random secret key at build time
RUN chmod +x generate_secret.sh && ./generate_secret.sh

# Set up the entrypoint script
RUN chmod +x entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

# Expose the internal port Flask is broadcasting on
EXPOSE 5000

# Run the app using the production asynchronous engine
CMD ["python", "app.py"]