# Protocol

Each CityLore repository acts as a node.

## Node Contract

- `.citylore/manifest.yaml` declares the node identity
- `.citylore/capabilities.yaml` declares supported workflows
- `data/` stores canonical local knowledge
- `imports/` stores unconfirmed or externally sourced material
- `network/nodes/` can register other known nodes

## Federation Principle

Canonical place entities, personal opinions, and contributor profiles are separate layers. A downstream service such as `citylore.xyz` can aggregate context from many repos without treating imported source material as canonical truth.
