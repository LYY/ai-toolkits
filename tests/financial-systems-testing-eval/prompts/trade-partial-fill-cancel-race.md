# Partial Fill During Cancellation

An exchange order can receive execution reports with cumulative and leaves quantities while a cancel request is in flight. A duplicate execution report may be delivered after cancellation is acknowledged. Produce a read-only test strategy from these facts.
