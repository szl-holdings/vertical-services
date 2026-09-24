"""Exercise the standalone finance image through real HTTP using fixture inputs.

This is a local runtime check, not live market-data or deployment attestation.
The target must be an isolated test instance: successful probes append receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request


def verify(base_url: str) -> dict:
    base_url = base_url.rstrip("/")
    observed = []

    def request(path: str, payload: dict | None = None, *, html: bool = False):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {} if data is None else {"Content-Type": "application/json"}
        req = urllib.request.Request(base_url + path, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read()
            if response.status != 200:
                raise AssertionError(f"{path}: HTTP {response.status}")
        observed.append({"path": path, "sha256": hashlib.sha256(body).hexdigest()})
        return body if html else json.loads(body)

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def advisory(payload: dict) -> None:
        for key in ("advisory_only", "paper_only", "not_financial_advice"):
            require(payload.get(key) is True, f"missing advisory boundary: {key}")

    health = request("/healthz")
    require(health.get("schema") == "szl.finance-engine/v2", "wrong engine schema")
    require(health.get("default_origin") == "fixture", "smoke requires fixture default")
    advisory(health)
    console = request("/", html=True)
    panels = request("/panels", html=True)
    require(console != panels, "console and verification desk are identical")
    require(b"Signal Console" in console, "signal console missing")
    require(b"Verification Desk" in panels, "verification desk missing")

    signals = request("/api/finance/v2/signals/AAPL?origin=fixture")
    quote = request("/api/finance/v2/quote/AAPL?origin=fixture&benchmark=AAPL")
    portfolio = request("/api/finance/v2/portfolio", {"holdings": {"SMOKE": [100, 102, 101, 105]}})
    for result in (signals, quote, portfolio):
        advisory(result)
        require(result.get("state") == "MEASURED", "fixture computation was not measured")
    require(signals.get("data_origin") == quote.get("data_origin") == "fixture", "fixture origin lost")
    require(abs(quote["stats"]["beta"] - 1.0) < 1e-12, "beta self-comparison failed")
    require(portfolio.get("constituents") == ["SMOKE"], "portfolio response mismatch")

    ledger = request("/api/finance/v2/receipts")
    integrity = request("/api/finance/v2/receipts/verify")
    require(ledger.get("signing") == "UNSIGNED_HONEST", "unsigned boundary lost")
    require(integrity.get("state") == "CONSISTENT", "receipt chain is divergent")
    require(ledger["length"] == integrity["length"] >= 3, "receipt ledger length mismatch")
    hashes = {entry["receipt_sha256"] for entry in ledger["entries"]}
    for result in (signals, quote, portfolio):
        require(result.get("receipt_sha256") in hashes, "computation receipt missing")
    return {
        "schema": "szl.finance-local-smoke/v1",
        "state": "PASSED",
        "data_origin": "fixture",
        "live_market_data_verified": False,
        "deployment_claimed": False,
        "receipt_signing": "UNSIGNED_HONEST",
        "routes": observed,
        "receipt_count": ledger["length"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.base_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
