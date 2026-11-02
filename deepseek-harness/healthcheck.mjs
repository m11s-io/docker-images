import { resolveBindHost, hostAuthority } from './bind-host.mjs'

try {
  const response = await fetch(`http://${hostAuthority(resolveBindHost())}/`, {
    redirect: 'manual', signal: AbortSignal.timeout(5000),
  })
  process.exit((response.status >= 200 && response.status < 400)
    || [401, 403].includes(response.status) ? 0 : 1)
} catch {
  process.exit(1)
}
