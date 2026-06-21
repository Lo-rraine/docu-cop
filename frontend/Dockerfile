FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install dependencies
RUN npm install -g pnpm && pnpm install --frozen-lockfile

# Copy source
COPY frontend . .

# Build (env vars must be set at build time for Vite)
# Railway will pass VITE_* vars automatically
RUN pnpm build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

# Install serve to run the SPA
RUN npm install -g serve

# Copy built artifacts from builder
COPY --from=builder /app/dist ./dist

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

CMD ["serve", "-s", "dist", "-l", "3000"]
