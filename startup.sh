#!/bin/bash

# Install dependencies explicitly from requirements
pip install -r requirements.txt

# Install necessary LaTeX packages (clearly already defined correctly by you)
apt-get update && apt-get install -y \
    texlive \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-extra-utils

# Run the Flask application explicitly with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
