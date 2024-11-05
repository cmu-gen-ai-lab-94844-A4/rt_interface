# Start from the official PyTorch image
FROM pytorch/pytorch:1.11.0-cuda11.3-cudnn8-runtime

# Install system dependencies
RUN apt-get update && \
    apt-get install -y gcc g++ libffi-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy the application code
COPY . /app

# Expose the application port if needed
# EXPOSE 5000

# Configure the container to run in an executed manner
ENTRYPOINT ["python"]

# Command to run the application
CMD ["view.py"]
