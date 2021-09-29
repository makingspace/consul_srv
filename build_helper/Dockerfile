FROM python:3.7-slim

ARG PYPI_URL

ENV APP_HOME=/app
ENV DEBIAN_FRONTEND=noninteractive

RUN echo "alias dir='ls -alh --color'" >> /etc/bash.bashrc && \
    apt-get update && \
    apt-get install -y --no-install-recommends bash curl busybox dumb-init && \
    pip install pipenv

ENV PYPI_URL=${PYPI_URL}

ENV PIPENV_VENV_IN_PROJECT=1 \
    PYTHONUNBUFFERED=1

COPY ./build_helper/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

COPY . /app

WORKDIR ${APP_HOME}
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["shell"]
