# ---- Builder Stage ----
# Use a specific Python version as the builder base
FROM python:3.11 AS builder

# Install uv using pip (we need pip just once to get uv)
RUN pip install uv

# Set the working directory
WORKDIR /app

# Create a virtual environment within the builder stage
# This keeps dependencies isolated and makes copying easier
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python -m venv $VIRTUAL_ENV

# Copy only the dependency definition file first to leverage Docker cache
COPY pyproject.toml* uv.lock* ./
# COPY requirements*.txt ./ # Uncomment this line if using requirements.txt instead

# Install dependencies using uv into the virtual environment
# --system is not needed as we are using a venv
# --no-cache prevents caching within the uv run itself (Docker layer cache is still used)
RUN uv sync --no-cache
# RUN uv pip install --no-cache . # Use this line if dependencies are defined in pyproject.toml

# Copy the rest of your application code
COPY . .

# ---- Runtime Stage ----
# Use a slim Python base image for the final stage
FROM python:3.11-slim-bookworm AS runtime

# Set the working directory
WORKDIR /app

# Create a non-root user 'uv' as recommended
# See: https://docs.astral.sh/uv/guides/integration/docker/#creating-a-non-root-user
RUN useradd --create-home --shell /bin/bash uv

# Copy the virtual environment with installed dependencies from the builder stage
# Ensure the 'uv' user owns these files
# See: https://docs.astral.sh/uv/guides/integration/docker/#copying-artifacts
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY --from=builder --chown=uv:uv ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copy the application code from the builder stage
# Ensure the 'uv' user owns these files
COPY --from=builder --chown=uv:uv /app /app

# Switch to the non-root user 'uv'
USER uv

# Expose the port the application runs on (default for Uvicorn is 8000)
EXPOSE 8000

# Command to run the application using Uvicorn served via the venv's uvicorn
# See: https://docs.astral.sh/uv/guides/integration/docker/#running-the-application
# Assumes your main file is 'main.py' and your FastAPI app instance is 'app'
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]