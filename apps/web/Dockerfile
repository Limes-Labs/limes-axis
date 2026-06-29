# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS pnpm-base

WORKDIR /app
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    NEXT_TELEMETRY_DISABLED=1

RUN corepack enable && corepack prepare pnpm@10.28.0 --activate

FROM pnpm-base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/schemas/package.json packages/schemas/package.json
RUN pnpm install --frozen-lockfile

FROM deps AS builder

COPY apps/web apps/web
COPY packages/schemas packages/schemas
RUN pnpm --filter @limes-axis/web build

FROM pnpm-base AS prod-deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/schemas/package.json packages/schemas/package.json
RUN pnpm install --prod --frozen-lockfile

FROM node:24-bookworm-slim AS runtime

WORKDIR /app
ENV HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    PORT=3000

RUN groupadd --system --gid 10001 axis \
    && useradd --system --uid 10001 --gid axis --home-dir /app --shell /usr/sbin/nologin axis

COPY --from=prod-deps --chown=axis:axis /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=prod-deps --chown=axis:axis /app/node_modules ./node_modules
COPY --from=prod-deps --chown=axis:axis /app/apps/web/package.json ./apps/web/package.json
COPY --from=prod-deps --chown=axis:axis /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=prod-deps --chown=axis:axis /app/packages/schemas/package.json ./packages/schemas/package.json
COPY --from=builder --chown=axis:axis /app/apps/web/.next ./apps/web/.next
COPY --from=builder --chown=axis:axis /app/apps/web/next.config.ts ./apps/web/next.config.ts

USER 10001
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then((r) => { if (!r.ok) process.exit(1); }).catch(() => process.exit(1))"

CMD ["sh", "-c", "cd apps/web && exec ./node_modules/.bin/next start"]
