# non-root user example <https://medium.com/@DahlitzF/run-python-applications-as-non-root-user-in-docker-containers-by-example-cba46a0ff384>

FROM python:3.13-slim

RUN pip install --upgrade pip && \
    apt-get update -qq && \
    apt-get install -y make build-essential libimage-exiftool-perl

RUN useradd -ms /bin/bash appuser
USER appuser
WORKDIR /app

ENV PATH="/home/appuser/.local/bin:${PATH}"

COPY --chown=appuser:appuser ./exifizer.py .

CMD [ "python3", "./exifizer.py", "--help" ]
