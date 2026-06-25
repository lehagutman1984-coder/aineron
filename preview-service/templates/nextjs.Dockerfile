# E2B custom template: Node.js 20 LTS + Next.js 14 + common packages pre-installed
# Build: e2b template build --name aineron-nextjs --dockerfile nextjs.Dockerfile
# After build: set E2B_TEMPLATE_NEXTJS=<template_id> in .env
FROM e2bdev/code-interpreter:latest

# Node.js 20 LTS is available in the base image — add common Next.js packages
RUN npm install -g \
    next@14 \
    react@18 \
    react-dom@18 \
    typescript@5 \
    @types/react@18 \
    @types/node@20 \
    tailwindcss@3 \
    autoprefixer@10 \
    postcss@8

WORKDIR /app
