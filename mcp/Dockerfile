# Multi-stage build for WODCraft MCP Server
FROM node:20-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./
RUN npm ci --only=production

# Copy TypeScript source and build configuration
COPY tsconfig.json ./
COPY src/ ./src/
COPY schemas/ ./schemas/
COPY data/ ./data/
COPY examples/ ./examples/

# Build the TypeScript application
RUN npm run build

# Production stage
FROM node:20-slim AS production

# Install runtime dependencies (Python for WODCraft CLI)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 -r nodejs && useradd -r -g nodejs -u 1001 nodejs

# Set working directory
WORKDIR /app

# Copy built application from builder stage
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/schemas ./schemas
COPY --from=builder --chown=nodejs:nodejs /app/data ./data
COPY --from=builder --chown=nodejs:nodejs /app/examples ./examples
COPY --from=builder --chown=nodejs:nodejs /app/package.json ./package.json

# Copy WODCraft Python CLI from the parent directory
COPY --chown=nodejs:nodejs ../src ./python-src
COPY --chown=nodejs:nodejs ../wodc_vnext ./wodc_vnext
COPY --chown=nodejs:nodejs ../setup.py ./setup.py
COPY --chown=nodejs:nodejs ../pyproject.toml ./pyproject.toml

# Install WODCraft Python package
RUN python3 -m pip install --no-cache-dir -e .

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 8080

# Set environment variables
ENV NODE_ENV=production
ENV WODCRAFT_PYTHON=python3
ENV WODCRAFT_MCP_DEBUG=0

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "
    const http = require('http');
    const options = {
      host: 'localhost',
      port: process.env.PORT || 8080,
      path: '/health',
      timeout: 2000,
    };
    const request = http.request(options, (res) => {
      if (res.statusCode === 200) {
        process.exit(0);
      } else {
        process.exit(1);
      }
    });
    request.on('error', () => process.exit(1));
    request.end();
  "

# Start the simple HTTP server
CMD ["npm", "run", "start:simple"]