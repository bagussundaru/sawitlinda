# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Baked in at build time: Next inlines NEXT_PUBLIC_* into the client bundle, so
# changing the API URL means rebuilding this image, not just restarting it.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup -g 10001 sawitscan && adduser -u 10001 -G sawitscan -D sawitscan

COPY --from=builder /app/public ./public
COPY --from=builder --chown=sawitscan:sawitscan /app/.next/standalone ./
COPY --from=builder --chown=sawitscan:sawitscan /app/.next/static ./.next/static

USER sawitscan
EXPOSE 3000
CMD ["node", "server.js"]
