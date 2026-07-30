# Worked example

A full pass with commentary. Read this for calibration when a rewrite is not
landing, or to see what the output format looks like in practice.

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

**What makes this so obviously AI generated?**
- Opens and closes with chatbot artifacts, so the frame gives it away before the content does.
- Paragraph 2 is three copula-avoidance sentences in a row with the same shape (`serves as` / `functions as` / `stands as`), preceded by a colon that just renames the clause.
- Every claim is about significance rather than about the tools. Nothing in it could be checked.
- The one attributed claim (`Industry observers have noted`) attributes to nobody, and the media list asserts importance instead of demonstrating it.

**Anything fabricated?** The source has no figures at all, so any number in the rewrite has to come from somewhere real or not appear. Two were available and verified rather than invented: GitHub's own reported acceptance rate, and the 2024 Uplevel Data Labs study of 800 developers. The `New York Times` / `Wired` / `Verge` mentions were dropped rather than kept, since C11 says a media list is not evidence of anything and the rewrite has real evidence instead.

**Final rewrite:**
> AI coding assistants speed up the parts of my job I don't much enjoy. Architecture isn't one of them.
>
> Boilerplate is where they earn it. Config files and test scaffolding, plus the kind of repetitive refactor that takes an hour and no thought. They're also very good at producing code that looks right, and I've accepted suggestions that compiled and passed lint while quietly doing the wrong thing, mostly because I'd stopped reading carefully by the fourth one.
>
> The people I've asked about this split roughly in half. Some treat it as autocomplete for chores and read every line before accepting. One team I know turned it off after it kept proposing patterns from an internal library they'd deprecated two years earlier.
>
> Measuring any of this is harder than it looks. GitHub reports that Copilot users accept around 30% of suggestions, though an accepted suggestion isn't necessarily a correct one. Uplevel Data Labs studied 800 developers in 2024 and found no meaningful difference in pull-request throughput between teams with Copilot and teams without, which is about what I'd expect if the gains are real but small enough to vanish into normal variance. I'm not confident about that reading.

**What I cut:** chatbot artifacts (`Great question!`, `I hope this helps!`) and the knowledge-cutoff hedge, Communication artifacts; significance inflation (`testament`, `pivotal moment`, `evolving landscape`, `vital role`) B1; promotional language (`groundbreaking`, `nestled`) C9; `-ing` pseudo-depth (`underscoring`, `fostering`) B2; negative parallelism (`It's not just about X; it's about Y`) B4; rule of three and synonym cycling B5/B7; false range (`from hobbyist experiments to enterprise-wide rollouts`) B6; copula avoidance (`serves as`, `functions as`, `stands as`) B3; stacked declaratives, the catalyst/partner/foundation run, B10; colon-restatement (`the value proposition is clear:`) B14; `At its core` C1; vague attribution (`Industry observers`) C10; notability name-dropping C11; em dashes and curly quotes C5/C6; stacked hedging (`could potentially… might have some`) D1; `In conclusion` and `the future looks bright` C8.

**What I added back:** first-person stance that reads spoken rather than literary (B17), two verifiable anchors where the original had none (D4), and an admission in the closing line instead of a resolution (A5, Soul item c).

**What's left I'm watching:** `harder than it looks` is a mild idiom that earns its keep but only just. `Boilerplate is where they earn it` is a short punchy opener to a paragraph and sits close to B10 territory. The third paragraph's two examples are nearly the same length, which is mild A2 uniformity, and I left it because forcing asymmetry there read worse.

**Battery result:** passes `--mode full` on every HARD and soft gate. CV 0.68, four sentences under 10 words, two over 30, paragraph ratio 3.8x, ten contractions, zero banlist hits, zero em dashes, zero tricolons.

Note that this file is expected to FAIL `score.py`, because the "Before" block is a deliberate specimen full of the tells the skill removes. See AGENTS.md on which files are battery fixtures.
