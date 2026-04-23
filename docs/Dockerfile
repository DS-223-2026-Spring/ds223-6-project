# ─────────────────────────────────────────────────────────────
#  Docs Service – MkDocs Material
#  Live documentation preview at http://localhost:8080
#  Any .md file saved in ./docs/ reloads instantly.
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /

RUN pip install --no-cache-dir \
    mkdocs==1.6.0 \
    mkdocs-material==9.5.25

COPY . .

# --dev-addr makes it accessible outside the container
CMD ["mkdocs", "serve", "--dev-addr=0.0.0.0:8080"]

EXPOSE 8080
