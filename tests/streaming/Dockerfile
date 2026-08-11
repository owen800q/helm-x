# Build helm-x on Linux and run the streaming-timeout verification test.
#   docker build -f tests/streaming/Dockerfile -t helmx-streaming-test .
#   docker run --rm helmx-streaming-test
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake curl ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j \
    && test -x build/helmx

RUN chmod +x tests/streaming/run_test.sh
CMD ["bash", "tests/streaming/run_test.sh"]
