# m11s Docker Images

[![Build and push](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml/badge.svg)](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Public Docker images published to [Docker Hub](https://hub.docker.com/u/m11s).

## Available Images

| Image | Description | Tags |
|-------|-------------|------|
| [m11s/rclone](https://hub.docker.com/r/m11s/rclone) | rclone with inotify-tools | `latest-inotify`, `1.74-inotify` |

## Quick Start

```bash
docker pull m11s/rclone:latest-inotify
```

## Publishing

Images are maintained in the private monorepo and published here via CI on push to `main`.
