# Use official Playwright Python image which comes with Chromium and system dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt .

# Install dependencies (using system python inside the container)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Run the scheduler script by default
CMD ["python", "social_tools/run_scheduler.py"]
