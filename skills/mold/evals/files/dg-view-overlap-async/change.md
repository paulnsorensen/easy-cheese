# Change: sync stock levels from the warehouse feed

The warehouse system publishes StockChanged events to a topic. The catalog service subscribes.
The catalog service updates its stock table when an event arrives. It does not reply to the warehouse.
A failed update goes to a dead-letter topic.
The spec must show the order of the steps. The steps use messages, not calls that wait.

Actors: buyer, catalog maintainer.

Tier: light.

Source: our own prompt.
