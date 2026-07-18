---
title: Meridian Tool Stack Articulation
tags: [meridian, talking-points]
---

# Meridian Tool Stack Articulation

## Why Terraform Over Manual Provisioning

Manual console changes don't leave an audit trail and don't scale past a handful of resources. Terraform gives a single source of truth for infrastructure and makes drift detectable instead of invisible. Full walkthrough in [[Terraform-Fundamentals]].

## Why GitOps Over a Long-Running CI Server

Meridian's deployment pipeline pulls changes into the cluster via GitOps rather than pushing them from a long-running Jenkins-style server — no server to patch and babysit, and the cluster's actual state is always reconciled against Git rather than trusted to have received the last push. See [[CICD-Pipeline-Walkthrough]] for the full pipeline shape.
