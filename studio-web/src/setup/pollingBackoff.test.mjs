/**
 * Lightweight Node assertion for nextPollDelayMs (mirrors helpers.ts).
 * Run: node studio-web/src/setup/pollingBackoff.test.mjs
 */
function nextPollDelayMs(consecutiveFailures, baseMs = 1200, maxMs = 30000) {
  if (consecutiveFailures <= 0) return baseMs;
  const exp = Math.min(consecutiveFailures, 6);
  return Math.min(maxMs, baseMs * 2 ** (exp - 1));
}

const cases = [
  [0, 1200],
  [1, 1200],
  [2, 2400],
  [3, 4800],
  [10, 30000],
];
for (const [failures, expected] of cases) {
  const actual = nextPollDelayMs(failures);
  if (actual !== expected) {
    console.error(`FAIL failures=${failures} expected=${expected} actual=${actual}`);
    process.exit(1);
  }
}
console.log("pollingBackoff.test.mjs: ok");
