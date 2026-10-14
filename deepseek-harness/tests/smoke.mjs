import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

assert.equal(process.getuid(), 10001, 'Smoke must run as the runtime user')
const home = await mkdtemp(join(tmpdir(), 'dsh-smoke-'))
const child = spawn('/usr/local/bin/dsh-entrypoint', [], {
  env: { ...process.env, DSH_HOME: home },
  stdio: ['ignore', 'pipe', 'pipe'],
})
const exited = once(child, 'exit')
let logs = ''
child.stdout.on('data', data => { logs += data })
child.stderr.on('data', data => { logs += data })
try {
  let token
  for (let attempt = 0; attempt < 300; attempt++) {
    assert.equal(child.exitCode, null, 'Harness exited during startup')
    assert.equal(child.signalCode, null, 'Harness was killed during startup')
    token = logs.match(/token=([A-Za-z0-9_-]+)/)?.[1]
    if (token) break
    await delay(100)
  }
  assert.ok(token, 'Harness did not become ready within 30 seconds')
  assert.doesNotMatch(logs, /did not activate|failed to import/)
  const login = await fetch(`http://127.0.0.1:3080/?token=${token}`, {
    redirect: 'manual', signal: AbortSignal.timeout(5000),
  })
  const cookie = login.headers.getSetCookie().map(value => value.split(';')[0]).join('; ')
  const page = [302, 303].includes(login.status)
    ? await fetch('http://127.0.0.1:3080/', { headers: { cookie }, signal: AbortSignal.timeout(5000) })
    : login
  assert.equal(page.status, 200)
  assert.match(await page.text(), /<html/)
  console.log('Harness startup, browser plugins, authenticated HTML, and UID 10001 passed')
} catch (error) {
  console.error(logs.replace(/token=[A-Za-z0-9_-]+/g, 'token=[redacted]'))
  throw error
} finally {
  child.kill('SIGTERM')
  const stopped = await Promise.race([exited.then(() => true), delay(5000, false, { ref: false })])
  if (!stopped) {
    child.kill('SIGKILL')
    await exited
  }
  await rm(home, { recursive: true, force: true })
  assert.ok(stopped, 'Harness did not stop within 5 seconds')
}
