# Update package list and install LaTeX in the background
(apt-get update && apt-get install -y texlive-latex-base texlive-fonts-recommended texlive-extra-utils texlive-latex-extra) &

# Start Gunicorn immediately
gunicorn -w 4 -b 0.0.0.0:8000 app:app
