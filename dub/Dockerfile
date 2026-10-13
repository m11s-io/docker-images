# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
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

FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1

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
