# Use an official Python runtime as a parent image
FROM python:3.11.5-slim

# Set the working directory
WORKDIR /app

# Add a non-root user
RUN useradd -m slackbot

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY main.py /app/

# Change ownership of the app directory
RUN chown -R slackbot:slackbot /app

# Switch to non-root user
USER slackbot

# Run the main script when the container launches
CMD ["python", "main.py"]
