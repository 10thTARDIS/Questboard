# ── Development stage ──────────────────────────────────────────────────────────
FROM node:20-alpine AS development

WORKDIR /app

# package*.json copies both package.json and package-lock.json (if present).
# npm install is used instead of npm ci so the build succeeds even without a
# pre-existing lockfile. Once built, commit the generated package-lock.json
# to the repository so future builds can use the faster `npm ci`.
COPY package*.json ./
RUN npm install

# In development, source is bind-mounted. node_modules lives inside the
# container as an anonymous volume so the host copy doesn't shadow it.

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# ── Build stage ────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build


# ── Production stage ───────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

# Remove default Nginx config
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
