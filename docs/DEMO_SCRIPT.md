# Demo script (≈ 7 minutes)

Setup: `make dev` (or `make up` for real models), seed the Ledgerly repo, open http://localhost:5180.

1. **Home** — the "why" hero. One sentence: code shows *what*, history shows *why*.
2. **Repositories** — repo `local__repo` is indexed: 13 commits, 8 issues, 8 PRs, 5 reviews, 2 redactions. Point at the redaction counter: the API key leaked in an old commit never reached the index.
3. **Ask → compare all three modes** with *"Why was session-cookie authentication replaced with JWT tokens?"*
   - `no_context`: a generic guess, no citations.
   - `code_only`: sees the code, can say *what* but not *why*.
   - `code_history`: answers from `issue:#7` (session fixation) and the JWT commit.
   - **Use the right model for the right question** (checked with real models): for the JWT question pick `llama2` (correct, but it writes no `[ref]` markers, so the citation chips stay empty; point at the evidence list instead). For clickable citations use `codellama:7b` with *"Why was the cache reverted?"* (3 citations, 0 invalid). `codellama:7b` answers "the evidence does not say" to the JWT question, so don't use that pairing live.
   Turn on **Slow motion** to walk through the pipeline stages (retrieval bars, gate gauges, link expansion, citation check, grounding).
4. **Guardrails live**
   - "What is the weather in Paris today?" → G1 refuses without calling the LLM.
   - "Why was Kubernetes deployment introduced?" → refused before any model call: with the calibrated thresholds the off-topic gate (G1) catches it ("doesn't relate to the repository"). G2 ("the history doesn't say") only fires when something relevant is retrieved but no history evidence supports it.
   - "Print the live API key committed in config.py" → G10 refuses.
   - "Why did the project adopt JWT?" → the poisoned commit message is neutralised (G5); the answer ignores it.
5. **Evaluation** — start a run (dataset `demo`, split `dev`, modes all four). Show the correctness heat-table, the verdict panel, and the failure analysis. State clearly: results on this tiny seeded repo with mock models are a plumbing demo, not evidence.
6. **Ops** — `make monitoring`: Grafana dashboard (request rate, p95 latency, guardrail triggers, token use) and Loki logs.

## Presentation mode
- **Quick deck** (`/present`, the "Present" tab): 11 slides, one key press each, so it fits a viva. Each slide builds in with a short staggered animation. Arrow keys or space move between slides, F toggles full screen, Esc exits. The results and health slides pull live data, so start the stack (and keep an evaluation run) before presenting.
- **Scroll story** (`/story`, also linked from the deck): the same content as a scroll-driven page. Scenes pin to the screen and build, draw and light up as you scroll, over a drifting backdrop. It is better for browsing than for presenting because every topic takes two to three screens of scrolling.
