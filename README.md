# Prompt Shields SDK

[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)

A Python SDK, HTTP gateway, and telemetry collector that build a live inventory of every AI model call your own code makes.

## The problem

Your organisation's AI risk register is built from what people told you they were building. Meanwhile any engineer with an API key can put a large language model into production in an afternoon, and nothing in your existing stack sees it: a cloud access security broker sees TLS to `api.openai.com` and nothing more, your enterprise architecture tool holds the systems inventory but not the models running inside them, and your data loss prevention controls never inspect the prompt payload. Without a discovery layer at the code level, the AI asset register you present to an auditor is a survey, not an inventory — and the gap between them is where unreviewed models handling regulated data live.

## Quickstart

```bash
git clone https://github.com/Bit-Pulse-AI/prompt-shields-sdk.git && cd prompt-shields-sdk
docker compose up -d
pip install -e "packages/collector[dev]" -e "packages/sdk[all]"
(cd packages/db && alembic upgrade head)
PYTHONPATH=packages:packages/collector python3 demo/seed_data.py && python3 demo/demo_sdk_flow.py
```

The demo seeds a registry, ships a synthetic event through the collector, and prints the discovered asset back out. Requires Docker and Python 3.11 or later.

## How does it work?

Three components write into one registry. **A telemetry collector is an HTTP service that receives structured records describing AI calls and reconciles them into a deduplicated asset inventory.** **An AI gateway is a proxy that sits on the HTTP path between an application and a model provider, so it can observe calls without the application being modified.** **An AI asset registry is a database of the distinct AI systems in use, each with an owner, a business unit, a data classification, and a confidence score.**

```
 Your code                          Your code (unmodified)
     |                                       |
     | ShieldsOpenAI / ShieldsAnthropic      | OPENAI_BASE_URL=gateway
     v                                       v
 +---------+                          +-------------+
 | Python  |                          | AI Gateway  |---> model provider
 |  SDK    |---> model provider       | (TypeScript)|
 +----+----+                          +------+------+
      |                                      |
      |          structured events           |
      +------------------+-------------------+
                         v
              +----------------------+
              | Telemetry Collector  |   fail-open: a collector
              |      (FastAPI)       |   outage never blocks a
              +----------+-----------+   model call
                         v
              +----------------------+
              | PostgreSQL + pgvector|   dedup, confidence scoring,
              |    Asset Registry    |   semantic search
              +----------+-----------+
                         v
                  Registry REST API
                         |
        +----------------+----------------+
        v                v                v
     Ardoq          ServiceNow        Custom REST
   (shipped)        (planned)          (shipped)
```

The SDK wraps the OpenAI and Anthropic clients and emits an event per call. **Fail-open means the telemetry path is allowed to fail silently: events buffer locally, up to 1000, with exponential-backoff retry, and the model call proceeds regardless.** The gateway covers applications you cannot or will not modify. The collector fingerprints incoming assets and assigns a confidence score of `low`, `medium`, `high`, or `verified` depending on how many independent sources corroborate them.

### What does the SDK capture?

| Captured | Notes |
|---|---|
| Vendor, model, tokens, latency, cost | Built-in pricing table for OpenAI, Anthropic, and Google models |
| Ownership metadata | Business unit, use case, owner, environment, data classification |
| PII categories | Pattern-based: email, phone, national insurance or social security number, payment card, IP address, IBAN, health data, financial data |
| Tool and function calls | OpenAI `tool_calls` and Anthropic `tool_use` blocks |
| API key fingerprint | Truncated SHA-256, never the raw key |
| Requested versus served model | Makes routing savings provable |

Prompt text is never transmitted unless you explicitly set `send_prompt_text=True`.

```python
from prompt_shields import ShieldsOpenAI

client = ShieldsOpenAI(
    api_key="sk-...",
    ps_api_key="ps-...",
    ps_collector_url="http://localhost:8000",
    business_unit="HR",
    use_case="interview-screening",
    owner="jane.doe@acme.com",
    data_classification="confidential",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Summarise this candidate..."}],
)
```

`AsyncShieldsOpenAI` and `ShieldsAnthropic` present the same surface. A deeper walkthrough is in [SDK_GUIDE.md](SDK_GUIDE.md).

### Running the tests

```bash
PYTHONPATH=packages:packages/collector python3 -m pytest packages/collector/tests -v
PYTHONPATH=packages/sdk python3 -m pytest packages/sdk/tests -v
```

## What this does not do

This is a discovery and inventory tool. It is not a runtime guardrail, and it should not be sold internally as one.

- **It does not block anything.** There is no enforcement path. A prompt containing regulated data is recorded and passed through. If you need a control that stops the call, this is not it.
- **PII detection is pattern-based and reports categories only.** Regular expressions over structured formats. It will miss free-text disclosure, names, and anything unusually formatted, and it will produce false positives on strings that merely look like an identifier. It records that a category was seen, never the matched value.
- **It does not see AI your staff use in a browser.** SDK and gateway instrumentation covers code paths only. Shadow use of ChatGPT or Claude by a person is a separate problem, covered by the endpoint clients documented at [docs.promptshields.com](https://docs.promptshields.com).
- **Gateway coverage is opt-in per application.** An application that keeps calling the provider directly, with no SDK and no rebased URL, stays invisible. Discovery completeness is a rollout property, not a technical guarantee.
- **Cost figures are estimates.** Computed from a local pricing table against observed token counts. They will not reconcile to a provider invoice.
- **Confidence scores are corroboration counts, not assurance.** A `verified` asset is one several sources agree on. It has not been reviewed by anyone.
- **No tamper-evidence in this repository.** Events are ordinary database rows. Nothing here produces an audit artefact that would survive a challenge to its integrity.
- **Self-hosting means you own the security of the deployment.** The collector holds tenant API keys and asset metadata. Network exposure, backups, patching, and key rotation are yours.

## Free versus Prompt Shields Cloud

The boundary is deliberate and published so it can be held to: **anything an individual engineer needs is free; anything an organisation or an auditor needs is paid.** No capability will be moved from the free side to the paid side.

| | Free — Apache 2.0, self-hosted | Prompt Shields Cloud |
|---|---|---|
| SDK, gateway, collector | Complete, no feature gating | Same code |
| Detection | Pattern-based scanners in this repository | Managed detection models, retrained continuously |
| Deployment | Self-hosted, single project, single user | Managed, multi-project, multi-tenant |
| Dashboard | Basic self-hosted registry views | Managed risk dashboard, OWASP LLM Top 10 and MITRE ATLAS mapping across traces |
| Telemetry | OpenTelemetry-compatible emission you store yourself | Hosted retention, cross-project alerting and anomaly detection |
| Governance | None | Organisation-wide policy enforcement, policy versioning and approval workflows, environment promotion, SSO and SAML, SCIM, RBAC |
| Compliance evidence | None | Hash-chained tamper-evident audit logs, EU AI Act Article 12 exports, one-click incident reports, NIST AI RMF and OWASP mapping tables |
| Data controls | Entirely yours | Bring-your-own keys, region pinning, air-gapped deployment |
| Support | Community issues, best effort | Service level agreements, named support, data processing agreement and penetration test report handling |

We do not monetise the code. We monetise hosting, enterprise controls, compliance evidence, and accountability. A fork can take the scanners; it cannot take the managed models, the certifications, or the service level agreement.

## Links

- Documentation: [docs.promptshields.com](https://docs.promptshields.com) — start at [Developers](https://docs.promptshields.com/developers/overview)
- Developer guide: [SDK_GUIDE.md](SDK_GUIDE.md)
- Security policy: [SECURITY.md](SECURITY.md) — report privately to security@promptshields.com, never via a public issue
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## Licence

Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

The `gateway/` directory is a fork of the [Portkey AI Gateway](https://github.com/Portkey-AI/gateway), licensed under the MIT Licence. That licence continues to govern the upstream code and is retained at [`gateway/LICENSE`](gateway/LICENSE); modifications are described in [`gateway/FORK_NOTICE.md`](gateway/FORK_NOTICE.md). MIT is compatible with Apache 2.0, so the combined work may be distributed under these terms provided both notices are preserved.
