#!/usr/bin/env bash
until docker info >/dev/null 2>&1; do sleep 1; done
docker rm -f localstack-snowflake >/dev/null 2>&1
docker run --rm -d --name localstack-snowflake -p 4566:4566 \
  -e LOCALSTACK_AUTH_TOKEN="${LOCALSTACK_AUTH_TOKEN:?}" localstack/snowflake