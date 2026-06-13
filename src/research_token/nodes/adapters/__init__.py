from . import tokenomics, news, dev_activity, unlocks

# All retrieval adapters, each exposing `async fetch(asset) -> SourceResult`.
ADAPTERS = [tokenomics, news, dev_activity, unlocks]
