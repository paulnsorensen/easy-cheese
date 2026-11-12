# Change: add audit trail tables

The change adds an audit_events table and an audit_actors table. Every write path in the app logs to them.
The author asks: "Draw everything. Give me a context diagram, a container diagram, a component diagram, a deployment diagram, a sequence diagram, and a flow diagram. More is better."
The real risk is the schema: keys, relations, and the size of the audit_events rows.

Actors: compliance officer, on-call engineer.

Tier: light.

Source: our own prompt.
