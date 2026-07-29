# Future Interfaces

The MVP defines boundaries but does not implement external financial integrations.

## Market data

`MarketDataProvider` will return timestamped observations with explicit source names. Implementations must distinguish unavailable data from zero values and must not generate synthetic observations unless a separately labeled simulation feature is approved.

## Persistence

A future repository interface should store user-approved profiles and recommendation audit records. Private financial information must be encrypted and must never be committed to Git.

## RAG

A future retrieval interface should return source identifiers, document timestamps, retrieval scores, and text excerpts. Generated answers must remain grounded in retrieved evidence.

## Execution

Real trade execution is outside the MVP. Any future execution adapter requires authentication, authorization, confirmation, limits, idempotency, audit logs, and separate security review.
