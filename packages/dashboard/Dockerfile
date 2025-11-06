# syntax=docker/dockerfile:1

# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Install serve for serving static files
RUN npm install -g serve

# Copy built assets from builder
COPY --from=builder /app/dist /app/dist

EXPOSE 5173

# Serve the built application
CMD ["serve", "-s", "dist", "-l", "5173"]