# start by pulling the python image
# Use Python 3.12 slim as base
# Use Python 3.12 slim as base
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libssl-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy just the requirements.txt first to leverage Docker cache
COPY requirements.txt /app/

# Install pip dependencies (cache layer)
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
RUN export LDFLAGS="-L/usr/local/opt/openssl/lib"

# Copy the rest of your application code into the container
COPY . /app

EXPOSE 5000

# Set environment variable
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Command to run your application
CMD ["python", "view.py"]



