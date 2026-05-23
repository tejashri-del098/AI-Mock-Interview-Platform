# Use a slim python base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Create a non-root user 'user' with UID 1000
RUN useradd -m -u 1000 user

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nginx \
    supervisor \
    git \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up app directory
WORKDIR /app

# Copy requirements file first to utilize Docker build cache
COPY requirements.txt /app/

# Install python dependencies system-wide
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary runtime directories and ensure correct ownership (run as root)
RUN mkdir -p /app/data/uploads /app/data/audio /app/data/reports /app/data/chromadb && \
    chown -R user:user /app

# Switch to non-root user
USER user

# Pre-cache Hugging Face Embeddings and Whisper model weights under user's home cache
RUN python -c "from langchain_community.embeddings import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2', model_kwargs={'device': 'cpu'})" && \
    python -c "import whisper; whisper.load_model('tiny')"

# Copy the rest of the application files with user ownership
COPY --chown=user:user . /app

# Expose the public port expected by Hugging Face Spaces
EXPOSE 7860

# Start supervisord to launch uvicorn, streamlit, and nginx processes
CMD ["supervisord", "-c", "/app/supervisord.conf"]
