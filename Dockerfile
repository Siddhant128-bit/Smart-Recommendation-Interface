# Base image with Python 3.12
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set writable Rust directories
ENV CARGO_HOME=/app/.cargo
ENV RUSTUP_HOME=/app/.rustup
ENV PATH="$CARGO_HOME/bin:$PATH"

# Install Rust via rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Copy requirements file
COPY requirements.txt .

# Upgrade pip, setuptools, wheel
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy the rest of your app
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
