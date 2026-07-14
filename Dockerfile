# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies, libpq-dev for Postgres, and Node.js 18
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ---- BACKEND SETUP ----
# Copy backend requirements to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Pre-download the Hugging Face models so they don't download on first request
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# ---- FRONTEND SETUP ----
# Copy frontend package files
COPY frontend/package*.json ./frontend/

# Install frontend dependencies
RUN cd frontend && npm install

# ---- COPY APP SOURCE ----
# Copy the rest of the application (both frontend and backend source code)
COPY . .

# Build the Next.js frontend for production
RUN cd frontend && npm run build

# Ensure the startup script is executable
RUN chmod +x start.sh

# Expose ports for both Backend (8000) and Frontend (3000)
EXPOSE 8000
EXPOSE 3000

# Set environment variables for production
ENV NODE_ENV=production

# Command to run all services simultaneously
CMD ["./start.sh"]
