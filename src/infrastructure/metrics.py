from prometheus_client import Counter, Gauge

proxy_tokens_input = Counter(
    "proxy_tokens_input_total",
    "Total input tokens proxied",
    ["account_id"],
)

proxy_tokens_output = Counter(
    "proxy_tokens_output_total",
    "Total output tokens proxied",
    ["account_id"],
)

proxy_active_connections = Gauge(
    "proxy_active_connections",
    "Current active connections per account",
    ["account_id"],
)
