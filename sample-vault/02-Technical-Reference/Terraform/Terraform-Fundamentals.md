---
title: Terraform Fundamentals
tags: [terraform, iac, aws]
aliases: [tf-fundamentals]
---

# Terraform Fundamentals

## Module Structure

Meridian's infrastructure is split by resource type rather than fully modularized — a `compute.tf`, a `network.tf`, and an `iam.tf` per environment. Modules become worth the overhead once there's more than one environment or vertical to manage; for a single-environment project the extra abstraction isn't paying for itself yet.

## State Management

### Drift Management

State drift happens when the real infrastructure diverges from what the state file records — usually from a manual console change made during an incident. Detecting it means running a plan on a schedule and treating any non-empty diff as a signal, not just relying on someone noticing later.

```hcl
resource "aws_instance" "app_server" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.medium"

  tags = {
    Project     = "Meridian"
    Environment = "prod"
  }
}
```

### State Locking

Team-wide state safety comes from locking the state file during writes — an S3 backend with DynamoDB-based locking prevents two people from applying at the same time and corrupting the state. See [[Meridian-Tool-Stack-Articulation]] for how this fits into the broader tool choices on this project.
