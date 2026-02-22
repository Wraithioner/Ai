FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    git \
    curl \
    dnsutils \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --production=false

COPY . .
RUN npm run build

RUN npm prune --production

CMD ["node", "dist/index.js"]
