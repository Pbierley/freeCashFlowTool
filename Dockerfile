# Use an official lightweight Python image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Copy only requirements first to leverage layer caching
COPY requirements.txt requirements-dev.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir -r requirements-dev.txt

# Copy the application code
COPY . /app

# Run tests by default to validate the container works
CMD ["pytest", "-q"]
