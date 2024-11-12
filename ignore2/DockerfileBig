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

# Upgrade pip, setuptools, and wheel
RUN pip install --upgrade pip setuptools wheel

# Install the basic and heavy libraries separatedly
RUN pip install pyarrow huggingface_hub transformers datasets nltk numpy Flask Flask-Session flask_session flask flask_cors openai psycopg2-binary flask-cors google-api-python-client google-auth google-auth-oauthlib python-dotenv setuptools wheel click colorama itsdangerous Jinja2 MarkupSafe Werkzeug gunicorn pandas pipenv postgres psycopg2-binary psycopg2-pool SQLAlchemy sqlparse datetime python-dotenv Authlib Flask-Dance Flask-Dance[sqla] uuid Flask-WTF

# Install torch-related packages with the specific index URL
RUN pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cpu

# Copy the rest of the application code into the image
COPY . /app

# Expose the Flask app port
EXPOSE 5000

# Set the entrypoint to execute Python scripts
ENTRYPOINT ["python"]

# Default command to run the Flask app
CMD ["view.py"]

