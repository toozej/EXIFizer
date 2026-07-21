# non-root user example <https://medium.com/@DahlitzF/run-python-applications-as-non-root-user-in-docker-containers-by-example-cba46a0ff384>

FROM python:3.14.6-slim

RUN pip install --upgrade pip && \
    apt-get update -qq && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends make build-essential libimage-exiftool-perl && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash appuser
USER appuser
WORKDIR /app

ENV PATH="/home/appuser/.local/bin:${PATH}"

COPY --chown=appuser:appuser ./exifizer.py .

CMD [ "python3", "./exifizer.py", "--help" ]
