# Hugging Face retired the Streamlit Space SDK, so the app ships as a Docker
# Space instead. Two things the platform requires: the server listens on 7860,
# and the process runs as uid 1000 -- root-owned caches make the Space fail on
# first write.
FROM python:3.12-slim

# opencv-python-headless still links libglib; libgomp is torch's OpenMP runtime.
# The X11 libraries are insurance: if a GUI build of opencv ever wins the
# resolution again, it imports instead of dying on libxcb.so.1.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgomp1 libgl1 libxcb1 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Dependencies first: the layer survives every later change to the source.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ultralytics declares opencv-python, so pip installs it over the headless build
# that requirements.txt asks for -- both distributions ship the same cv2 module
# and the last one written wins. The GUI build then fails at import on libxcb.
# Removing it and reinstating headless leaves ultralytics working, because the
# import name is unchanged.
RUN pip uninstall -y opencv-python opencv-contrib-python || true \
    && pip install --no-cache-dir --force-reinstall \
        opencv-python-headless==5.0.0.93

COPY --chown=user . .

EXPOSE 7860
CMD ["streamlit", "run", "app.py", \
     "--server.port=7860", "--server.address=0.0.0.0"]
