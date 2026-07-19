# Payment Provider Timeout

A payment service sends a charge request with an idempotency key. The provider times out after receiving the request, and a later webhook may arrive with a settled or rejected outcome. Produce a read-only test strategy from these facts.
