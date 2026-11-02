import assert from 'node:assert/strict'
import { test } from 'node:test'
import { resolveBindHost, hostAuthority } from '../bind-host.mjs'

const interfaces = {
  lo: [{ address: '127.0.0.1', family: 'IPv4', internal: true }],
  eth0: [{ address: '172.18.0.2', family: 'IPv4', internal: false }],
}
test('selects the concrete container address rather than wildcard or loopback', () => {
  assert.equal(resolveBindHost({}, interfaces), '172.18.0.2')
})
test('explicit binding supports loopback and IPv6', () => {
  assert.equal(resolveBindHost({ DSH_BIND_HOST: '127.0.0.1' }, interfaces), '127.0.0.1')
  assert.equal(hostAuthority('::1'), '[::1]:3080')
})
test('rejects wildcard addresses and non-IP configuration', () => {
  for (const host of ['0.0.0.0', '::', '::ffff:0.0.0.0', 'localhost', 'bad\nhost']) {
    assert.throws(() => resolveBindHost({ DSH_BIND_HOST: host }, interfaces), /concrete/)
  }
})
test('requires explicit selection when there is no unambiguous container IPv4', () => {
  assert.throws(() => resolveBindHost({}, {}), /DSH_BIND_HOST/)
  assert.throws(() => resolveBindHost({}, { ...interfaces,
    eth1: [{ address: '172.19.0.2', family: 'IPv4', internal: false }],
  }), /DSH_BIND_HOST/)
})
