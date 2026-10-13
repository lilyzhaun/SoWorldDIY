/** Wait for a committed browser-rendered state, rather than assuming timer order. */
export async function waitForRender(condition: () => boolean): Promise<void> {
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  const deadline = performance.now() + 2000
  while (performance.now() < deadline) {
    if (condition()) return
    await new Promise<void>((resolve) => window.setTimeout(resolve, 10))
  }
  throw new Error('Expected React state did not commit within 2 seconds')
}
