# Change: run the API in two regions

The API runs in one region on three nodes. The change adds a second region.
Each region has a load balancer, three API nodes, and a read replica of the database.
The primary database stays in region one. Region two writes through a cross-region link.
The structure of the API does not change. Only where it runs changes.

Actors: API client, on-call engineer.

Tier: light.

Source: our own prompt.
