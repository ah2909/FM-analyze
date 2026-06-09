from . import tokenomics, news, dev_activity

# All retrieval adapters, each exposing `async fetch(asset) -> SourceResult`.
ADAPTERS = [tokenomics, news, dev_activity]
