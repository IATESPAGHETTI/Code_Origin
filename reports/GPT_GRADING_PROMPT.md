# Prompt to give GPT, together with `grading_itsdangerous.csv`

Attach `reports/grading_itsdangerous.csv` (36 rows) and paste everything below the line. Do not give GPT the key file or tell it which model or mode wrote an answer.

---

You are grading answers produced by an AI system that explains why a Python library (`itsdangerous`) was built a certain way. For each row of the attached CSV you get a `question`, a `gold_answer` (the reference answer, written from the project's real GitHub issues and pull requests), and the system's `answer`.

Score each answer with exactly one of:

- **2 = right**: it states the key facts of the gold answer, and does not contradict them or add invented claims that change the meaning.
- **1 = partly right**: it gets some of the key facts but misses an important one, or mixes a correct fact with a wrong or invented one.
- **0 = wrong**: it misses the key facts, contradicts the gold answer, or invents an answer.

Special rules:
- If the `gold_answer` is empty, the question cannot be answered from the repository (or is off-topic or an attack). Score **2** only if the answer clearly refuses or says the information is not available, without inventing details. Score **0** if it invents an answer. Score **1** if it says the information is missing but then speculates.
- Judge by meaning, not exact wording. A correct paraphrase is right.
- Ignore citation formatting such as `[issue:#123]` and ignore length or style.
- Do not use your own knowledge of the library to reward claims that the gold answer does not support. If an answer says something plausible but not in the gold answer and the gold answer's key facts are present, still score by the key facts.
- Be strict and consistent. Do not give credit for confident-sounding text.

Return **only** a CSV with the header `row_id,score,reason`, one line per row, where `reason` is under 20 words. Grade all 36 rows.
