---
title: Interview-Ready Troubleshooting Stories
tags: [troubleshooting, star-stories]
---

# Interview-Ready Troubleshooting Stories

## Jenkins Agent Could Not Reach the Docker Daemon

### Situation

A pipeline stage that containerized the application started failing on a freshly provisioned build agent, even though the Docker plugin was installed and configured in Jenkins.

### Task

Get the containerize step working again without weakening the agent's security posture.

### Action

Confirmed the Docker plugin only manages Jenkins-side configuration — it doesn't grant the agent access to an actual Docker daemon. Mounted the host's Docker socket into the agent container so `docker build` had somewhere real to run against.

### Result

The pipeline went green again, and the fix became the standard bootstrap step for any new build agent going forward.
