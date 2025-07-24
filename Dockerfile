FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose the port Fly expects
ENV PORT 8080

# Start the server on 0.0.0.0:8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

