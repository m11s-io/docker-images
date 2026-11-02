import { isIP } from 'node:net'
import { networkInterfaces } from 'node:os'
import { pathToFileURL } from 'node:url'

export function resolveBindHost(env = process.env, interfaces = networkInterfaces()) {
  if (env.DSH_BIND_HOST) {
    const host = env.DSH_BIND_HOST
    const family = isIP(host)
    const normalized = family === 6 ? new URL(`http://[${host}]/`).hostname : host
    if (!family || ['0.0.0.0', '[::]', '[::ffff:0:0]'].includes(normalized)) {
      throw new Error('DSH_BIND_HOST must be a concrete IPv4 or IPv6 address')
    }
    return host
  }
  const addresses = [...new Set(Object.values(interfaces).flat().filter(
    item => item && !item.internal && item.family === 'IPv4',
  ).map(item => item.address))]
  if (addresses.length !== 1) {
    throw new Error('Set DSH_BIND_HOST to one concrete local IP address; automatic selection requires exactly one non-loopback IPv4 address')
  }
  return addresses[0]
}

export function hostAuthority(host) {
  return `${isIP(host) === 6 ? `[${host}]` : host}:3080`
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(resolveBindHost())
}
