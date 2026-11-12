# Development: dependencies only, the source is mounted and served by `vite dev`
FROM node:24-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# Production build
FROM dev AS build
RUN npm run build && npm prune --omit=dev

# Production: only the built server, running as the unprivileged node user
FROM node:24-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build --chown=node:node /app/build ./build
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/package.json ./
USER node
EXPOSE 3000
CMD ["node", "build"]
