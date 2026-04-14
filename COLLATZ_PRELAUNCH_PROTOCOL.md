# Collatz Prelaunch Protocol

This protocol prepares Lima for a serious Collatz run using the wild invention
plus mathematical baking loop.

## Principle

Lima may hallucinate mathematical worlds during invention. Lima may not treat
any invention as progress until it survives falsification and creates proof debt
that can be baked by evidence, Aristotle, or a human.

## Loop

1. Create a Collatz campaign.
2. Run a wild invention batch.
3. Distill raw inventions into candidate worlds.
4. Run cheap falsifiers.
5. Promote a surviving world.
6. Bake proof debt through the normal execution loop.
7. Feed failures, dead patterns, and proved debt back into self-improvement.

## API Sequence

```http
POST /api/campaigns
POST /api/campaigns/{campaign_id}/invention/batches
POST /api/campaigns/{campaign_id}/invention/batches/{batch_id}/distill
POST /api/campaigns/{campaign_id}/invention/batches/{batch_id}/falsify
POST /api/campaigns/{campaign_id}/invention/worlds/promote
POST /api/campaigns/{campaign_id}/step
GET  /api/campaigns/{campaign_id}/operator-brief
GET  /api/campaigns/{campaign_id}/invention/lab
```

Default invention payload:

```json
{
  "mode": "wild",
  "wildness": "high",
  "requested_worlds": 30
}
```

## Readiness Gates

- Unit tests pass with `python -m pytest -q`.
- Structured obligations persist as structured memory payloads.
- Invention lab records raw worlds, distilled worlds, falsifiers, proof debt,
  and promoted active worlds.
- Operator brief shows invention counts, promising worlds, and dead patterns.
- Self-improvement may tune invention prompts and scoring, but cannot modify
  verdict semantics or solved criteria.

## Collatz Launch Contract

We are trying to solve Collatz. The system may invent aggressively.

It may only declare closure when:

1. the active world has a bridge back to Collatz;
2. all critical proof debt is formally proved;
3. no live critical falsifier remains unresolved;
4. final proof artifacts are replayable.
