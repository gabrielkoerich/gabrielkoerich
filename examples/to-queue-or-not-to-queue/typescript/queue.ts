export {} // each example is its own module

type Transfer = { id: string; amount: number } // id is the idempotency key

// A bounded queue: put waits while the queue is full, take waits while it is empty
class BoundedQueue<T> {
  private items: T[] = []
  private waitingTakers: Array<(item: T | undefined) => void> = []
  private waitingPutters: Array<() => void> = []
  private closed = false
  private capacity: number

  constructor(capacity: number) {
    this.capacity = capacity
  }

  async put(item: T): Promise<void> {
    while (this.items.length >= this.capacity) {
      await new Promise<void>(resolve => this.waitingPutters.push(resolve))
    }

    const taker = this.waitingTakers.shift()
    if (taker) {
      taker(item)
    } else {
      this.items.push(item)
    }
  }

  async take(): Promise<T | undefined> {
    const item = this.items.shift()
    if (item !== undefined) {
      this.waitingPutters.shift()?.()
      return item
    }

    if (this.closed) {
      return undefined
    }

    return new Promise(resolve => this.waitingTakers.push(resolve))
  }

  close() {
    this.closed = true
    for (const taker of this.waitingTakers.splice(0)) {
      taker(undefined)
    }
  }
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
const settle = async (_t: Transfer) => sleep(20) // the slow side effect

async function worker(queue: BoundedQueue<Transfer>, seen: Set<string>) {
  let handled = 0
  for (let t = await queue.take(); t !== undefined; t = await queue.take()) {
    if (seen.has(t.id)) {
      continue // delivered twice, already settled
    }

    seen.add(t.id)
    await settle(t)
    handled++
  }

  return handled
}

async function main() {
  const queue = new BoundedQueue<Transfer>(4)
  const seen = new Set<string>()
  const workers = [worker(queue, seen), worker(queue, seen)]

  const start = performance.now()
  let slowestSend = 0
  for (let i = 0; i < 40; i++) {
    const t0 = performance.now()
    await queue.put({ id: `tx${i % 30}:0`, amount: i }) // ten duplicates
    slowestSend = Math.max(slowestSend, performance.now() - t0)
  }

  queue.close()
  const total = (await Promise.all(workers)).reduce((a, b) => a + b, 0)
  console.log(`queue: settled ${total} of 40 messages (30 unique) in ${Math.round(performance.now() - start)}ms, slowest put waited ${Math.round(slowestSend)}ms`)
}

main()
