# Problem: image pull credentials for private registries

A node agent pulls container images from private registries. Today it holds credential code for each cloud registry inside its own binary.

A cluster operator who uses a new registry must wait for a release of the node agent. The maintainers of the node agent must keep and test vendor code that they do not own.

The credentials are short-lived. A pull happens on the node's hot path, so a slow lookup delays a pod start.

Existing clusters that use the built-in code must keep working while the change lands.

Actors: cluster operator, node agent maintainer, registry vendor.

Tier: full.

Source: <https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/2133-kubelet-credential-providers/README.md>. The upstream text is Apache-2.0. This fixture is our own paraphrase and copies no sentence.
