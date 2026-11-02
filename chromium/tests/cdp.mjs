import assert from 'node:assert/strict'

const endpoint = 'http://chromium:9222'
let version
for (let attempt = 0; attempt < 30; attempt++) {
  try {
    const response = await fetch(`${endpoint}/json/version`, { signal: AbortSignal.timeout(1000) })
    assert.equal(response.status, 200)
    version = await response.json()
    break
  } catch (error) {
    if (attempt === 29) throw error
    await new Promise(resolve => setTimeout(resolve, 500))
  }
}
assert.equal(new URL(version.webSocketDebuggerUrl).host, 'chromium:9222')
const socket = new WebSocket(version.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error('CDP WebSocket timed out')), 5000)
  socket.addEventListener('open', () => socket.send(JSON.stringify({ id: 1, method: 'Browser.getVersion' })))
  socket.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('CDP WebSocket failed')) })
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data)
    if (message.id !== 1) return
    clearTimeout(timeout)
    try { assert.ok(message.result.product.startsWith('Chrome/')); resolve() } catch (error) { reject(error) }
    socket.close()
  })
})
console.log(`CDP discovery and WebSocket connection passed: ${version.Browser}`)
