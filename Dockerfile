# Use an official Python slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create working directory
WORKDIR /app

# Install system dependencies and LaTeX
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-extra-utils \
    texlive-latex-extra \
    latexmk \
    gnupg \
    curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Remove conflicting ODBC packages BEFORE installing msodbcsql18
RUN apt-get update && \
    apt-get remove -y libodbc2 libodbcinst2 unixodbc-common && \
    curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app code into the container
COPY . .

# Make startup script executable
RUN chmod +x startup.sh

# Set permissions for Flask session storage
RUN mkdir -p /tmp/flask_session

# Expose the app port
EXPOSE 8000

# Default command
CMD ["./startup.sh"]
