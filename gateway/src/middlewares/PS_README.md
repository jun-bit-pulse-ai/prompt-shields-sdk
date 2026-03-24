# Prompt Shields Gateway Extensions

This directory contains Prompt Shields-specific middleware added on top of the Portkey AI Gateway.

## ps-telemetry.ts

Intercepts all LLM requests flowing through the gateway and sends discovery telemetry
to the Prompt Shields collector service. This enables zero-code-change AI asset discovery
for any application that routes LLM traffic through the gateway.

### How it works

1. **Before request:** Extracts `X-PS-*` headers for business metadata, strips them before forwarding
2. **After response:** Captures vendor, model, token usage, latency, and sends to collector
3. **Fail-open:** Telemetry failures never block LLM requests

### Configuration

Set these environment variables:
- `PS_COLLECTOR_URL` — URL of the Prompt Shields collector (default: `http://localhost:8000`)
- `PS_API_KEY` — Prompt Shields API key for authentication

### X-PS-* Headers

Applications can annotate requests with business context via HTTP headers:
- `X-PS-Business-Unit` — e.g., "HR", "Legal"
- `X-PS-Use-Case` — e.g., "interview-screening"
- `X-PS-Owner` — e.g., "jane.doe@acme.com"
- `X-PS-Data-Classification` — e.g., "confidential"
- `X-PS-Environment` — e.g., "production"
