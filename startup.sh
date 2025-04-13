#!/bin/bash

# Update package list and install system dependencies
apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-extra-utils \
    texlive-latex-extra \
    latexmk

# Install Python dependencies AFTER system dependencies
pip install -r requirements.txt

# Start Gunicorn with increased timeout for large requests
gunicorn -w 4 -b 0.0.0.0:8000 app:app
