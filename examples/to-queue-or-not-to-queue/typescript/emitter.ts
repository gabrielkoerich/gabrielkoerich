import { EventEmitter } from 'node:events'

const bus = new EventEmitter({ captureRejections: true })

bus.on('transfer', (id: string) => console.log(`saved ${id}`))
bus.on('transfer', async (id: string) => {
  await new Promise(r => setTimeout(r, 10))
  throw new Error(`notify failed for ${id}`)
})
bus.on('error', (e: Error) => console.log(`error event: ${e.message}`))

console.log('before emit')
const hadListeners = bus.emit('transfer', 'tx1:0')
console.log(`after emit, returned ${hadListeners}, nothing was awaited`)
