# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the bot source code into the container
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Define environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the bot
CMD ["python", "butler.py", "run_bot", "-c", "config" "test-bot"]
