# Problem: the network before the rack is up

When a rack powers on for the first time, its compute sleds must find each other and a bootstrap agent. No managed network service runs yet.

The design must pick the shape of the bootstrap network: one shared broadcast domain, or routed links between sleds and switches. There is no address server, and the installer has little time.

The choice sets how failures spread, how addresses form, and how much switch setup the installer does.

## Recorded user decisions

The user made these choices in an earlier dialogue round. They are not agent decisions.

- D-1 (user): routed layer 3 links between each sled and each switch, not one shared broadcast domain. The user rejected the shared domain, because one broadcast fault reaches every sled. The user rejected a hybrid, because it adds both sets of failure modes.
- D-2 (user): each sled derives its address from its slot, so no address server is needed. Peer discovery stays a separate requirement.
- Open (no user decision yet): what a sled does when it sits in the wrong slot.

Actors: installer who brings up a rack, firmware engineer, rack operator.

Tier: full.

Source: <https://rfd.shared.oxide.computer/rfd/0063>. The upstream site grants no reuse license. This fixture paraphrases the topic and copies no sentence.
