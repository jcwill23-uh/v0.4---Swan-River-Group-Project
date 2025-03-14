# Update package list and install LaTeX
apt-get update && apt-get install -y texlive-latex-base texlive-fonts-recommended texlive-extra-utils texlive-latex-extra

# Start Gunicorn to serve Flask app
gunicorn -w 4 -b 0.0.0.0:8000 app:app
