export {} // each example is its own module

class Retryable extends Error {}
class Permanent extends Error {}

const BASE_MS = 100
const CAP_MS = 2_000
const MAX_ATTEMPTS = 5

// Full jitter: a random wait between zero and the exponential ceiling
const backoff = (attempt: number) => Math.random() * Math.min(CAP_MS, BASE_MS * 2 ** attempt)
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

async function settle(id: string, attempt: number): Promise<void> {
  if (id === 'bad') {
    throw new Permanent('unknown account')
  }

  if (id === 'flaky' && attempt < 3) {
    throw new Retryable('timeout')
  }

  if (id === 'down') {
    throw new Retryable('503')
  }
}

async function handle(id: string, deadLetters: Array<[string, string]>) {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      await settle(id, attempt)
      console.log(`${id}: settled on attempt ${attempt}`)
      return
    } catch (e) {
      if (!(e instanceof Retryable)) {
        deadLetters.push([id, String((e as Error).message)]) // retrying cannot fix it
        return
      }

      if (attempt === MAX_ATTEMPTS) {
        deadLetters.push([id, `gave up after ${attempt}: ${e.message}`])
        return
      }

      await sleep(backoff(attempt))
    }
  }
}

async function main() {
  const deadLetters: Array<[string, string]> = []
  for (const id of ['ok', 'flaky', 'bad', 'down']) {
    await handle(id, deadLetters)
  }

  console.log(`dead letters: ${deadLetters.map(([id, why]) => `${id} (${why})`).join(', ')}`)
}

main()
