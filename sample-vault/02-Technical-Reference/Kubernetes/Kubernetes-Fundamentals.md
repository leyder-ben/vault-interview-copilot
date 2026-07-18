---
title: Kubernetes Fundamentals
tags: [kubernetes, scaling]
---

# Kubernetes Fundamentals

## Pod Scaling vs Node Scaling

The Horizontal Pod Autoscaler (HPA) scales the number of pod replicas based on observed CPU or memory usage. It has nothing to do with how many nodes exist underneath — that's the Cluster Autoscaler's job, which adds or removes nodes based on whether pending pods can actually be scheduled on current capacity.

## HPA Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: meridian-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: meridian-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Cluster Autoscaler

The Cluster Autoscaler is configured through the Terraform node group's min/max size settings, not through a Kubernetes manifest — see [[Terraform-Fundamentals]] for where that lives.
