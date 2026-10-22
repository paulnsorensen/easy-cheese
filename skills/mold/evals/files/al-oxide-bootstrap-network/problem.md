# Problem: the network before the rack is up

When a rack powers on for the first time, its compute sleds must find each other and a bootstrap agent. No managed network service runs yet.

The design must pick the shape of the bootstrap network: one shared broadcast domain, or routed links between sleds and switches. There is no address server, and the installer has little time.

The choice sets how failures spread, how addresses form, and how much switch setup the installer does.

Actors: installer who brings up a rack, firmware engineer, rack operator.

Tier: full.

Source: <https://rfd.shared.oxide.computer/rfd/0063>. The upstream site grants no reuse license. This fixture paraphrases the topic and copies no sentence.
