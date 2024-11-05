# Start by pulling the python image
FROM python:3.12-rc-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch working directory
WORKDIR /app

# Install build dependencies
RUN apk update && \
    apk add --no-cache --virtual .build-deps gcc g++ musl-dev \
    libffi-dev openssl-dev python3-dev make

# Optional: Add runtime dependencies (depending on requirements of pyarrow etc.)
RUN apk add --no-cache libstdc++ bash

# Copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# Install the dependencies and packages in the requirements file
RUN pip install --upgrade pip setuptools wheel && \
    pip install numpy && \
    pip install -r /app/requirements.txt

# Remove build dependencies
RUN apk del .build-deps

# Copy every content from the local file to the image
COPY . /app

# Expose the application port
EXPOSE 5000

# Configure the container to run in an executed manner
ENTRYPOINT [ "python" ]

# Command to run the application
CMD ["view.py"]


