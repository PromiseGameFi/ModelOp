# Scheduler State Machine

## States

- `queued`: waiting for a free slot.
- `active`: allocated in batch and receiving decode steps.
- `finished`: emitted EOS or hit max token limit.
- `evicted`: removed due to policy or timeout.

## Transitions

- `queued -> active`: free slot + budget available.
- `active -> finished`: EOS emitted or generation cap reached.
- `active -> evicted`: explicit cancellation or policy eviction.
- `finished -> removed`: cleanup in same tick.

## Tick Requirements

- Run decode for each active sequence once per tick.
- Process finished cleanup before refill.
- Refill slots from queue immediately after cleanup.
