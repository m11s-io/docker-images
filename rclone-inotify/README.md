# m11s/rclone

[`rclone`](https://rclone.org/) with `inotify-tools` added to the official
image. Use it when an rclone job needs to react to Linux filesystem events.

## Tags

| Tag | Use |
| --- | --- |
| `latest-inotify` | Current rclone image with `inotify-tools` |
| `1.74-inotify` | Pinned published rclone release |

## Usage

```bash
docker run --rm -v "$PWD:/data" m11s/rclone:latest-inotify \
  rclone sync /data remote:backup
```

Run `inotifywait` directly when a container needs to wait for a file event:

```bash
docker run --rm -v "$PWD:/data" m11s/rclone:latest-inotify \
  inotifywait -m /data
```

See the [rclone documentation](https://rclone.org/docs/) for remote
configuration and command options. Source and license: [m11s-io/docker-images](https://github.com/m11s-io/docker-images).
