# Architecture Diagrams

Each diagram is provided in two forms:
- **Source**: `.md` with Mermaid fenced code blocks (editable, diff-friendly).
- **Export**: `.svg` (vector, rendered by any browser or Markdown viewer).

| Diagram | Source (Mermaid) | Export (SVG) | Purpose |
|---|---|---|---|
| Component overview | `component.md` | `component.svg` | Full system layout: client, API, packages, data, models. |
| Class — Inference Gateway | `class_inference_gateway.md` | `class_inference_gateway.svg` | Strategy / Adapter / Decorator / Circuit Breaker relationships. |
| Class — RAG Core | `class_rag_core.md` | `class_rag_core.svg` | Repository / Strategy / Pipeline / Observer / Registry / Factory. |
| Sequence — Chat flow | `sequence_chat.md` | `sequence_chat.svg` | Three execution paths: cache hit, cache miss, primary-failure failover. |

The `.svg` files are hand-rendered vector exports of the Mermaid sources.
They are committed to make the diagrams readable in environments that do
not render Mermaid (GitHub mobile, terminals, static site generators
without a Mermaid plugin). Any change to the `.md` source should be
mirrored in the `.svg` export.

## Reusability boundary

The two packages under `packages/` have independent `pyproject.toml`
files, their own test suites, and **zero imports from `apps/`**. This is
intentional and load-bearing: a downstream consumer can `pip install`
`rag_core` and `inference_gateway` into a fresh project without pulling
in the FastAPI application.
