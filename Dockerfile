FROM ubuntu:bionic

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gpg \
        fonts-hanazono \
        fonts-noto-cjk \
        fonts-noto-hinted \
        fonts-noto-unhinted \
        mapnik-utils \
        ttf-unifont \
        fontconfig \
        nodejs \
        node-mapnik \
        node-carto \
        node-srs \
        node-zipfile \
        python3-mapnik \
        python3-pil \
        python3-gdal \
        gdal-bin \
    && curl -sL -o /usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf https://github.com/googlei18n/noto-emoji/raw/master/fonts/NotoEmoji-Regular.ttf \
    && fc-config -rv

