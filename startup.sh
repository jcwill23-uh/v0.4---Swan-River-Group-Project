# Update package list and install LaTeX
apt-get update && apt-get install -y texlive-latex-base texlive-fonts-recommended texlive-extra-utils texlive-latex-extra

# Start Gunicorn to serve Flask app
gunicorn app:app
