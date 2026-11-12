# Problem: a store for control plane state

A rack-scale cloud product needs one store for its control plane state. The state covers instances, disks, and networks.

The state is relational. Writes must be consistent. The store must keep working when one machine fails, and it must grow by adding machines.

The store ships inside an appliance. Its license must allow that. The team has little operating experience with the leading candidate, so its maturity is uncertain.

## Recorded user decisions

The user made this choice in an earlier dialogue round. It is not an agent decision.

- D-1 (user): a distributed SQL store. The user rejected a single-writer replicated store, because it does not meet the required write scale-out. The user rejected a key-value store, because it moves relational queries and consistency into application code. The user accepted the operating-maturity risk and named the platform lead as the owner of an early fault test.
- Open (no user decision yet): nobody has confirmed that the license of the chosen store allows shipping it inside the appliance.

Actors: control plane developer, rack operator, customer who needs the API to stay up.

Tier: full.

Source: <https://rfd.shared.oxide.computer/rfd/0110>. The upstream site grants no reuse license. This fixture paraphrases the topic and copies no sentence.
