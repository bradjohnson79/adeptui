import assert from "node:assert/strict";
import test from "node:test";
import { isDiagnosticsResult, readFaultDomain } from "./diagnosticsResult.ts";

test("rejects 504/error JSON without classification or layers", () => {
  assert.equal(isDiagnosticsResult({ error: "Gateway Timeout" }), false);
  assert.equal(isDiagnosticsResult({ status: 504, message: "upstream timeout" }), false);
  assert.equal(isDiagnosticsResult({ classification: { faultDomain: "HEALTHY" } }), false);
  assert.equal(isDiagnosticsResult({ layers: { ports: [] } }), false);
  assert.equal(isDiagnosticsResult(null), false);
  assert.equal(isDiagnosticsResult(undefined), false);
});

test("accepts a DiagnosticsResult-shaped body", () => {
  assert.equal(
    isDiagnosticsResult({
      classification: { faultDomain: "HEALTHY", confidence: "high", evidence: "ok" },
      layers: { ports: [] },
      totalMs: 12,
    }),
    true,
  );
});

test("undefined classification does not throw", () => {
  assert.doesNotThrow(() => readFaultDomain({}));
  assert.doesNotThrow(() => readFaultDomain({ classification: undefined, layers: {} }));
  assert.equal(readFaultDomain({}), undefined);
  assert.equal(readFaultDomain({ classification: { faultDomain: "DEGRADED" } }), "DEGRADED");
});