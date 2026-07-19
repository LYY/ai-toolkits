# Concurrent Work Queue

A Go service has an in-memory work queue. Two workers can dequeue the same job when a lock is released too early. No financial data or business state is involved. Produce a read-only test strategy from these facts.
