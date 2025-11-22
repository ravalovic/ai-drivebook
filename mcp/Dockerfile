FROM python:3.11-slim

WORKDIR /app

# Aby geopy/Nominatim nepadali kvôli SSL/locale
RUN apt-get update && apt-get install -y \
    ca-certificates \
    locales \
 && rm -rf /var/lib/apt/lists/*

RUN sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY mcp.json .

EXPOSE 8000

CMD ["python", "server.py"]
