# `frontier_fabric`

Shared Python contracts for SZL's flagship and vertical products.

```python
from frontier_fabric import EvaluationRequest, VerticalFabric

fabric = VerticalFabric()
result = fabric.evaluate(
    EvaluationRequest(
        vertical_id="lyte",
        signal_id="deployment-42",
        session_id="operator-session",
        actor_id="operator",
        payload={
            "service": "checkout",
            "lambda_axes": [0.96, 0.93, 0.91],
        },
    )
)

assert result.decision.value == "HOLD"
assert result.proposal.state.value == "UNAVAILABLE"
```

The default result is intentionally `HOLD`: no model or kernel is considered
live because a repository exists. Register exact model and kernel adapters,
provide a reviewed proposal, and bind a human approval before a consequential
adapter can advance.

Primary documentation:

- [`docs/VERTICAL_FRONTIER_FABRIC_V1.md`](../docs/VERTICAL_FRONTIER_FABRIC_V1.md)
- [`docs/CHAMPION_PATTERN_LEDGER.md`](../docs/CHAMPION_PATTERN_LEDGER.md)
- [`docs/OPEN_SOURCE_AND_DATA_INTAKE_POLICY.md`](../docs/OPEN_SOURCE_AND_DATA_INTAKE_POLICY.md)
