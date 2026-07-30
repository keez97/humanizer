# Worked example

A full before/after pass with commentary. Read this for calibration when a
rewrite is not landing, or to see what the output format looks like in practice.

**Before (AI-sounding):**
> Great question! Here is an essay on this topic. I hope this helps!
>
> AI-assisted coding serves as an enduring testament to the transformative potential of large language models, marking a pivotal moment in the evolution of software development. In today's rapidly evolving technological landscape, these groundbreaking tools—nestled at the intersection of research and practice—are reshaping how engineers ideate, iterate, and deliver, underscoring their vital role in modern workflows.
>
> At its core, the value proposition is clear: streamlining processes, enhancing collaboration, and fostering alignment. It's not just about autocomplete; it's about unlocking creativity at scale. The tool serves as a catalyst. The assistant functions as a partner. The system stands as a foundation for innovation.
>
> Industry observers have noted that adoption has accelerated from hobbyist experiments to enterprise-wide rollouts. The technology has been featured in The New York Times, Wired, and The Verge.
>
> While specific details are limited based on available information, it could potentially be argued that these tools might have some positive effect. In conclusion, the future looks bright. Let me know if you'd like me to expand on any section!

**Final rewrite:**
> AI coding assistants can make you faster at the boring parts. Not everything. Definitely not architecture.
>
> They're great at boilerplate: config files, test scaffolding, repetitive refactors. They're also great at sounding right while being wrong. I've accepted suggestions that compiled, passed lint, and still missed the point because I stopped paying attention.
>
> People I talk to tend to land in two camps. Some use it like autocomplete for chores and review every line. Others disabled it after it kept suggesting patterns from a deprecated internal library. Both feel reasonable.
>
> The productivity metrics are slippery. GitHub can say Copilot users "accept 30% of suggestions," but acceptance isn't correctness, and correctness isn't value. The 2024 Uplevel study found no significant difference in pull-request throughput between teams with and without AI assistants. If you don't have tests, you're basically guessing.

**What I cut:** chatbot artifacts ("Great question!", "I hope this helps!") — Comm; significance inflation ("testament", "pivotal moment", "evolving landscape", "vital role") — B1; promotional language ("groundbreaking", "nestled") — C9; vague attribution ("Industry observers") — C10; -ing pseudo-depth ("underscoring", "fostering") — B2; negative parallelism ("not just X; it's Y") — B4; stacked declaratives ("catalyst / partner / foundation") — B10; "At its core" — C1; rule-of-three and synonym cycling — B5/B7; false range ("from hobbyist to enterprise") — B6; em dashes / boldface / curly quotes — C5/C6; copula avoidance ("serves as", "functions as", "stands as") — B3; knowledge-cutoff hedge — Comm; excessive hedging ("could potentially… might have some") — D1; "In conclusion / the future looks bright" — C8/Comm.

**What's left I'm watching:** "slippery" is a mild idiom that earns its keep but only just; "Both feel reasonable" is a voiced closer that's slightly tidy; the Uplevel citation must be real and sourced or it reads as a plausible-but-invented placeholder.

