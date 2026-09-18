# Phase 4 external vocabulary pins

The Phase 4 transformer performs no network access. Its ELI and ELI-DL terms
were audited against the following immutable content identities:

| Vocabulary | Version | Source | SHA-256 |
|---|---|---|---|
| ELI | 1.5 | `ontology/ELI-OWL/eli-1.5.rdf` (source: `https://data.europa.eu/eli/ontology#`) | `35bba63a0945e089817ddeb25512d31bfa101344282a4dfbce58e92ad756111c` |
| ELI-DL | 3.0 | `ontology/ELI-DL-OWL/eli-dl.ttl` | `5ec2d7a0bb176e1432e39fee3e4150c3f651dafaef52976428259be4f9eabb62` |

Both ELI 1.5 and ELI-DL 3.0 are vendored at the paths above. Their checksums
are verified before Phase 4 vocabulary coverage is assessed; no runtime network
dependency exists.
