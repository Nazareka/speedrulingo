# Speedrulingo

Speedrulingo is a language-learning app in the general category of Duolingo, but with a different product philosophy and learning experience.

The main goal of the project is to create a faster, more streamlined, and explanation-first alternative to traditional language-learning apps. Instead of focusing on a wide variety of exercise types such as speaking tasks, dialogue simulations, stories, or open-ended conversations with AI, Speedrulingo is centered around a smaller set of core learning activities: vocabulary, sentence comprehension, word selection, and sentence building.

The idea is to make the learning loop lightweight and efficient, so users can move through lessons very quickly without unnecessary friction. At the same time, the app aims to provide something that tools like Duolingo still lack: instant, one-click explanations for both words and sentences.

This comes from a real user need. When using apps like Duolingo, it is often necessary to manually copy a word or sentence into ChatGPT and ask for an explanation of what it means, how it works, and how it should be understood. Speedrulingo is designed to bring that experience directly into the product. Instead of leaving the app and asking an external AI tool for help, the learner should be able to get useful explanations immediately inside the lesson flow.

Another major goal of the project is to generate the course itself with the help of LLMs. ChatGPT can be used during the configuration stage to research educational resources and help define the course structure. Then, based on that configuration, including sections, grammar patterns, themes, section descriptions, and example constraints, an LLM can generate the vocabulary base and sentence base used by the app. In the long term, the vision is not just to build a learning interface, but to build a system capable of generating a complete structured language course with a strong focus on speed, clarity, and explanation-first learning.

## Why This Project Is Interesting

- It combines a regular product stack with an LLM-driven content generation pipeline.
- It includes a non-trivial course builder with staged planning, assembly, and release checks.
- It focuses on a concrete product problem, not just a generic "AI demo".

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Postgres, Pydantic, LangGraph, LangChain OpenAI
- Frontend: React, Vite, TypeScript, TanStack Router, TanStack Query
- Tooling: Ruff, Mypy, Pytest, Vitest, Biome, ast-grep, Docker Compose

## What Is Already Working

- Vocabulary generation from course configuration
- Sentence generation from course configuration
- Config-driven course structure with sections, themes, and grammar patterns
- A usable lesson flow inside the app
- A lesson page that is already in relatively decent shape compared to the rest of the UI

## Current State

At the moment, the project is already able to generate vocabulary and sentences based on a configuration that defines the course structure, including sections, grammar patterns, themes, and related constraints. Right now, the configured sections are `PRE_A1`, `A1_1`, `A1_2`, and `A2_1`.

The current vocabulary generation is already reasonably good and mostly aligned with the intended learning progression. However, there are still some important gaps, especially around specific basic words and number-related vocabulary. For example, some numerals and closely related words should appear earlier and in a more logical order. Learners should encounter words such as 1, 2, 3, 4, 5, 6, 8, 9, and 10 before seeing expressions like “9 o’clock,” “10 o’clock,” “what time is it,” and other time-related or number-dependent vocabulary.

As for sentence generation, the current pipeline already produces usable results. Based on ChatGPT’s evaluation, around 80% of the generated sentences are good pedagogical sentences. This means the system is already functional, but there is still clear room to improve quality and consistency.

## Token Budget and Development Constraints

One important practical constraint during development has been token usage.

At the moment, generating the current course range, from `PRE_A1` through `A2_1`, requires roughly 500,000 to 700,000 tokens in total. The pipeline currently uses GPT-5.4 with low reasoning for this generation process.

During development, I had access to OpenAI’s complimentary daily token program for shared API traffic, which I used as part of my workflow. More details about the program are available here: [Sharing feedback, evaluation and fine-tuning data, and API inputs and outputs with OpenAI](https://help.openai.com/en/articles/10306912-sharing-feedback-evaluation-and-fine-tuning-data-and-api-inputs-and-outputs-with-openai).

In practice, I had a daily budget of 1 million tokens available for GPT-5.4, and one of the practical challenges during development was keeping the pipeline within that limit.

Because of that, token efficiency was not just a cost consideration. It directly influenced prompting, generation strategy, and overall pipeline design.

## What Still Needs Work

The frontend is still unfinished. The app is already usable and lessons can be completed, but the frontend remains visually rough, especially on pages other than the lesson page itself. The lesson page is in relatively good shape, but the rest of the UI still needs significant improvement.

Some smaller details are also incomplete. For example, hints do not always display correctly, and in some cases they are missing or shown in the wrong way. Distractors are currently too simple and should be made more sophisticated and more challenging.

Unit description generation is also not working properly at the moment and needs to be improved or redesigned.

## Planned Improvements

One obvious next step is improving sentence quality further, ideally from the current ~80% level to 95% or even higher. The course configuration can also be improved, and the current prompting / LLM output strategy still likely has room for refinement.

Another possible improvement is adding post-generation validation for LLM outputs. During development, the goal was to avoid this as much as possible in order to keep the system simpler and first push the base pipeline to produce the best possible results on its own. However, a post-LLM validation layer may still be worth considering. For example, generated output could be passed through another LLM-based validation step to check whether a sentence is natural, correct, and pedagogically appropriate.

A major planned feature is LLM-generated explanations for each sentence, available on demand when the user wants more detail. Similarly, each word should also have a separate LLM-generated explanation. The goal is not just to provide a short hint, but a more complete mini-article explaining what the word means, how it is used, and in what contexts it typically appears.

Another important missing feature is a proper kanji page. It should display kanji in chronological learning order, show which kanji have already been learned and which ones were introduced recently, and explain in which words each kanji appears.

It would also be very useful to add audio for sentences, words, and kanji. This should realistically be possible through a service such as ElevenLabs.

## Long-Term Vision

The long-term vision of Speedrulingo is to become a language-learning system that is faster, clearer, and more useful than traditional gamified apps for learners who care most about understanding. Instead of trying to offer every possible type of exercise, the project focuses on a smaller set of high-value interactions: learning vocabulary, understanding sentence structure, building sentences, and getting immediate explanations when something is unclear.

In that sense, Speedrulingo is not only a language-learning app, but also an experiment in using LLMs to generate and power an entire structured course from the ground up.

## Repository Layout

- [backend/](/Users/nazareka/projects/Speedrulingo/backend) FastAPI API, domain logic, database models, course builder, and LLM workflows
- [frontend/](/Users/nazareka/projects/Speedrulingo/frontend) React web app
- [docker-compose.yml](/Users/nazareka/projects/Speedrulingo/docker-compose.yml) local development stack
- [run_backend_tests_postgres.sh](/Users/nazareka/projects/Speedrulingo/run_backend_tests_postgres.sh) backend test runner against Postgres

## Local Development

### Backend

See [backend/README.md](/Users/nazareka/projects/Speedrulingo/backend/README.md).

### Frontend

See [frontend/README.md](/Users/nazareka/projects/Speedrulingo/frontend/README.md).

### Docker

You can also run the local stack with:

```bash
docker compose up --build
```

This starts:

- Postgres
- FastAPI backend
- Vite frontend dev server

## License

This project is open source under the MIT License. See [LICENSE](/Users/nazareka/projects/Speedrulingo/LICENSE).
