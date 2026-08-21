import { vi } from 'vitest'

/**
 * A mock of every function the API client exports, derived from the client itself.
 *
 * Hand-written mocks listed each function by name, so adding one to the client
 * broke four test files at once and always for the same reason: a component now
 * calls something the mock has never heard of. Deriving the shape from the real
 * module means a new client function is mocked the moment it exists.
 *
 * Every function resolves to undefined by default, so a component that awaits
 * one it does not care about gets a promise rather than a crash. Tests override
 * the ones they are about with mockResolvedValue.
 *
 * `errorMessage` is passed through rather than mocked: it is a pure formatter,
 * and tests assert on the message it produces.
 *
 * Use it as:
 *   vi.mock('../src/api/client', async (importOriginal) =>
 *     (await import('./mockClient')).mockClient(importOriginal))
 */
export async function mockClient(importOriginal) {
  const actual = await importOriginal()
  const mocked = {}
  for (const [name, value] of Object.entries(actual)) {
    mocked[name] = typeof value === 'function' ? vi.fn().mockResolvedValue(undefined) : value
  }
  return {
    ...mocked,
    errorMessage: (error, fallback) => error?.message ?? fallback ?? 'error',
  }
}
