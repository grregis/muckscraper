# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install system dependencies (Debian/Ubuntu)
RUN apt update && \
    apt install -y \
    python3-dev \
    libpq-dev \
    && apt clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY app/ .

# Expose the port the app runs on
EXPOSE 5000

# Run the app
CMD ["python", "main.py"]
