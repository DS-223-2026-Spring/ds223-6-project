# ─────────────────────────────────────────────────────────────
#  Frontend Service – React (Node 20)
#  Dashboard with ROI charts and budget optimizer.
#  Dev server at http://localhost:3000
# ─────────────────────────────────────────────────────────────

FROM node:20-alpine

WORKDIR /app

# Copy package files first for Docker layer caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy the rest of the app
COPY . .

# Expose React dev server port
EXPOSE 3000

# Start React development server
# CHOKIDAR_USEPOLLING makes file-watching work inside Docker on Mac/Windows
ENV CHOKIDAR_USEPOLLING=true
CMD ["npm", "start"]
