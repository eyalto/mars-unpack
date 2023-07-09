FROM ubuntu:22.10

RUN apt-get update && apt install -y gdb procps

RUN apt install -y python3.11

RUN apt install -y python3-pip

RUN pip install debugpy

ENV DEBUGPY_LOG_DIR=/logs
