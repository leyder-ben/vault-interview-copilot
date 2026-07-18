---
title: CICD Pipeline Walkthrough
tags: [cicd, github-actions]
---

# CICD Pipeline Walkthrough

## Build Stage

Every push builds a container image and runs a security scan before anything is allowed to be pushed to the registry.

```yaml
name: build
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t meridian-api:${{ github.sha }} .
      - name: Scan image
        run: trivy image meridian-api:${{ github.sha }}
      - name: Push to registry
        run: docker push meridian-api:${{ github.sha }}
```

## Deploy Stage

The build stage pushes an image; it does not touch the cluster directly. A separate GitOps controller notices the new image reference and reconciles the cluster to match — see [[Meridian-Tool-Stack-Articulation]] for the reasoning behind that split.
