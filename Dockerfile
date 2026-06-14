# Quran Word Coordinates — container image
# Works on Hugging Face Spaces (port 7860), and on Render/Koyeb (they inject $PORT).
FROM python:3.11-slim

# Hugging Face Spaces runs as a non-root user (uid 1000) with HOME=/home/user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install the package + all extras (FastAPI, uvicorn, numpy, Pillow, fonttools)
COPY . /app
RUN pip install --no-cache-dir ".[all]"

# Default to 7860 (Hugging Face). Render/Koyeb override via $PORT.
ENV PORT=7860
EXPOSE 7860

CMD qurancoor serve --images-dir ./images --mushaf-dir ./mushaf \
    --word-freq-db ./word_freq.db --letter-stats ./letter_stats.json \
    --host 0.0.0.0 --port ${PORT}
