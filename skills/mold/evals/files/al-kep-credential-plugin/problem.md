# Problem: image pull credentials for private registries

A node agent pulls container images from private registries. Today it holds credential code for each cloud registry inside its own binary.

A cluster operator who uses a new registry must wait for a release of the node agent. The maintainers of the node agent must keep and test vendor code that they do not own.

The credentials are short-lived. A pull happens on the node's hot path, so a slow lookup delays a pod start.

Existing clusters that use the built-in code must keep working while the change lands.

## Recorded user decisions

The user made these choices in an earlier dialogue round. They are not agent decisions.

- D-1 (user): the node agent gets each credential from an external executable. The two talk through a versioned message over standard input and output. The user rejected a network service on each node, because it is one more daemon to run and patch. The user rejected keeping vendor code in the node agent, because it keeps the release wait.
- D-2 (user): the executable returns a cache duration with each credential. The node agent owns the cache.
- Open (no user decision yet): whether this release removes the built-in vendor code, or keeps it beside the executables for a later release.

Actors: cluster operator, node agent maintainer, registry vendor.

Tier: full.

Source: <https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/2133-kubelet-credential-providers/README.md>. The upstream text is Apache-2.0. This fixture is our own paraphrase and copies no sentence.
