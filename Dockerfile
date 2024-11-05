# Use an official Python image based on a Debian Buster as the base image
FROM python:3.12-rc-buster

# Set the working directory within the image
WORKDIR /app

# Copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# Set environment variables to prevent Python from writing bytecode and buffering outputs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Ensure system packages are up-to-date and install necessary dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libopenblas-dev \
    libssl-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*  # Clean up the package lists

# Upgrade pip, setuptools, and wheel, then install libraries specified in requirements.txt
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r /app/requirements.txt

# Copy the rest of the application code into the image
COPY . /app

# Expose the Flask app port
EXPOSE 5000

# Set the entrypoint to execute Python scripts
ENTRYPOINT ["python"]

# Default command to run the Flask app
CMD ["view.py"]



