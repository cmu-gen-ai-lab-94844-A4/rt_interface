FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y gcc g++ libffi-dev libssl-dev

# Copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install numpy && \
    pip install -r requirements.txt

# Copy the application code
COPY . /app

# Expose the application port
EXPOSE 5000

# Configure the container to run in an executed manner
ENTRYPOINT [ "python" ]

# Command to run the application
CMD ["view.py"]

