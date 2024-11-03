# start by pulling the python image
# Use the Python 3.12 Alpine base image
FROM python:3.12-rc-alpine

# Install system dependencies needed for building Python packages
RUN apk update && apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    cmake \
    git

# Set the working directory
WORKDIR /app

# Copy the dependencies file and install dependencies
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
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



