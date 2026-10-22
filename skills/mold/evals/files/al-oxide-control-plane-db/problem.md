# Problem: a store for control plane state

A rack-scale cloud product needs one store for its control plane state. The state covers instances, disks, and networks.

The state is relational. Writes must be consistent. The store must keep working when one machine fails, and it must grow by adding machines.

The store ships inside an appliance. Its license must allow that. The team has little operating experience with the leading candidate, so its maturity is uncertain.

Actors: control plane developer, rack operator, customer who needs the API to stay up.

Tier: full.

Source: <https://rfd.shared.oxide.computer/rfd/0110>. The upstream site grants no reuse license. This fixture paraphrases the topic and copies no sentence.
