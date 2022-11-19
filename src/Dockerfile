FROM alpine:latest
MAINTAINER manasmbellani

RUN apk add bash \
    python3 \
    py3-pip \
    git

RUN git clone https://github.com/manasmbellani/pyengine

COPY . /app
WORKDIR /app

RUN python3 -m pip install -r requirements.txt