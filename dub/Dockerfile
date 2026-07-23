# syntax=docker/dockerfile:1
#
# Pre-built image: build the app locally first, then run this Dockerfile.
#
# Build steps (run from .third_party/dub):
#   pnpm install --frozen-lockfile
#   DATABASE_URL=mysql://x:x@localhost/x NEXTAUTH_SECRET=x NEXTAUTH_URL=http://localhost:3000 \
#     NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS="--max-old-space-size=4096" \
#     pnpm --filter web build
#
# Then build the image (from .third_party/dub):
#   docker build -f ../../platform/docker-images-public/dub/Dockerfile -t dub .

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --chown=nextjs:nodejs apps/web/.next/standalone ./
COPY --chown=nextjs:nodejs apps/web/.next/static ./apps/web/.next/static
COPY --chown=nextjs:nodejs apps/web/public ./apps/web/public

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "apps/web/server.js"]
