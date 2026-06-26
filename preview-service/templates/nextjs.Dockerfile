# E2B custom template: Next.js 14 with project-local node_modules prebaked
# L1 cold-start fix: base deps in /opt/base/node_modules (not -g global).
# Projects symlink /opt/base/node_modules → delta-install only if deps differ.
#
# Build: cd preview-service/templates && e2b template build --name aineron-nextjs --dockerfile nextjs.Dockerfile
# After build: set E2B_TEMPLATE_NEXTJS=<template_id> in .env
FROM e2bdev/code-interpreter:latest

WORKDIR /opt/base
COPY base-package.json /opt/base/package.json

# Install project-local (not -g global) so /opt/base/node_modules exists.
# --legacy-peer-deps: tolerate peer conflicts common in Next.js 14 ecosystem.
RUN npm install --legacy-peer-deps

# Write deps manifest so _bg_start_nextjs can detect whether delta-install needed.
RUN node -e " \
    const p = require('./package.json'); \
    const fs = require('fs'); \
    fs.writeFileSync('/opt/base/deps.json', \
      JSON.stringify(p.dependencies || {}) \
    ); \
  "

WORKDIR /app
