#!/bin/bash

PYPI_URL=`ssh ubuntu@baikonur.mksp.co consul kv get pypi/index_url`

if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac OSX
    export DOCKER_BUILDKIT=1
fi

docker build \
    --build-arg PYPI_URL=${PYPI_URL} \
    -f ./build_helper/Dockerfile \
    -t consul_srv_builder .
