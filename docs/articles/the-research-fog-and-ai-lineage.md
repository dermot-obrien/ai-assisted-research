# The Researcher's Fog of Discovery (and why AI needs a lineage of ideas)

*A guide to navigating the search space of ideas, avoiding research debt, and preparing for agentic discovery.*

In the early 1990s, I was at Edinburgh University during the foundation stages of the [Edinburgh Parallel Computing Centre (EPCC)](https://www.epcc.ed.ac.uk/), pursuing my PhD in neural networks under Professor David Wallace. Back then, the primary bottleneck was compute. Even with access to what was becoming one of the world's leading supercomputing centres, we had to be surgical with our ideas because the machines were slow, and every experiment was a significant investment of time. Today, that constraint has vanished. We have nearly infinite compute and, with the advent of AI agents, an almost infinite supply of hypotheses. But we’ve traded one bottleneck for another: we are now drowning in the very thing we sought.

We call this the *Fog of Discovery*. It’s that disorienting mental exhaustion that hits when you’ve generated so many threads of exploration with AI that you can no longer trace the "why" behind your current experiment. You feel like you're moving at light speed, but you're often just walking in very fast circles.

And here’s the uncomfortable truth: if you think AI is the simple cure for this chaos, you’re likely about to make it worse. Adding AI agents to an unmapped research process is like putting a jet engine on a car with no steering wheel. You’ll cover more ground, sure, but you’ll also hit the dead ends at 200 miles per hour.

I’ve spent over 40 years in the IT industry, building AI-driven systems for everything from time series prediction to enterprise platform strategy. I’ve seen first-hand how research projects don’t usually fail because of a lack of ideas, they fail because of *Research Debt*: the accumulated cost of forgotten context, unrecorded failures, and the inability to trace why a certain path was taken and why other paths were not taken.

In a [previous article](https://www.dermot-obrien.com/before-ai-can-help-you-fix-your-cognitive-load/), I explored how the "Architect's Cognitive Load" is driven by open loops and the psychological tax of unfinished work for IT professionals. The fix there was simple: Work-in-Progress (WIP) limits. But research is a different beast. In IT solutions and architecture, the work is often about execution of known patterns; in research, the work is about discovery in a fog of unknowns.

In this article, we'll look at the science of why discovery is so cognitively demanding, why your existing WIP limits might not be enough for research, and how to build the scaffolding that allows AI agents to actually do the heavy lifting for you.

## The Search Space Problem: Your Brain vs. The Infinite

At its core, research is a search through a massive, often infinite, solution space. Every decision you make, which variable to tune, which paper to read next, which algorithm to try, is a step in that space.

### The Exploration-Exploitation Trade-off

The fundamental challenge in any search is the *Exploration-Exploitation trade-off*.[^1] Do you exploit what you already know (refine the current model) or do you explore new territory (try a completely different approach)?

When we work manually, our internal WIP limits naturally constrain us. We can only hold so much in our heads. But AI removes those physical constraints. An AI agent can suggest 50 new exploration paths in seconds. If you don't have a map to place those paths on, your cognitive load explodes as you try to decide which ones are worth the compute cost. As at March 2026, new models such as Google Gemini 3.1 Pro and Anthropic Claude Opus 4.6 make fast work of understanding the state of the art (SOTA) and coming up with suggestions for new research directions. Whether AI should be used for hypothesis generation is a legitimate debate, but the reality is that researchers are already doing it, and the practice is accelerating. The more pressing question is how to do it with discipline.

### From Architecture to Research: The Zeigarnik Effect

As I discussed in my [Cognitive Load article](https://www.dermot-obrien.com/before-ai-can-help-you-fix-your-cognitive-load/), the Zeigarnik Effect shows that unfinished tasks persist in memory, pulling at our attention.[^2] In research, every "What if...?" is an open loop. "What if we changed the learning rate?" "What if the data bias is actually in the pre-processing?" 

If these loops aren't closed with a clear finding and recorded in a lineage, they linger. They become *Research Debt*. You end up re-testing the same assumptions six months later because the original evidence was buried in a message thread or an old commit message that just says "minor fixes."

## The Fix: Metric-Driven Lineage

To clear the fog, you need more than just a folder of notes. You need a *Lineage of Ideas*. 

In the same way that IT professionals need to limit their WIP to maintain quality, researchers need to structure their discovery into a *Lineage Graph*: a directed acyclic graph (DAG) where each node represents a finding and each edge represents the reasoning that prompted the next step.[^5]

This isn't just a plan. It's a requirement for agentic research work. A lineage of ideas requires three things:

1.  *Metric Supremacy*: Every hypothesis must be tied to a quantifiable target. In computational and empirical research, if you can't measure it, you can't know whether you've moved forward or sideways.
2.  *Lineage Continuity*: Every experiment must be able to answer: "What finding prompted this work?" and "What did we learn that we didn't know before?"
3.  *Atomic Evolution*: Each node in your graph should represent one fundamental change. This prevents "entangled variables" where you don't know which change actually caused the result.

### The "One In, One Out" Rule for Hypotheses

Just as we limit active projects to three at a time to avoid what Newport calls the overhead tax,[^3] we should limit active research hypotheses. If you're chasing five different breakthroughs at once, the attention residue between them ensures you'll do a mediocre job on all of them.[^4]

The discipline is simple: *Start fewer things, finish more loops.*

## Why AI Agents Need Structure More Than You Do

This brings us to the most critical point: AI agents are incredible at execution, but terrible at navigation without a map.

If you give an AI agent a vague goal like "optimize this model," it will churn through tokens and produce hallucinated progress: reams of plausible-looking output that cycles through the same dead ends from slightly different angles, giving the impression of momentum without actually advancing your understanding.

But if you give it a structured work item within a hypothesis map, something interesting happens. You stop being the person who runs every experiment and start being the person who decides which experiments are worth running. You become the orchestrator, the navigator. The agents do the traversal, the computation, the systematic elimination of dead ends. But the intuition about where to look next, the instinct that says "this result doesn't feel right" or "that anomaly is worth chasing," that stays with you. AI can't replicate the researcher's nose for a promising lead. What it can do is free you from the mechanical work so you actually have the time and headspace to follow it.

### The AI-Assisted Research Framework

To put these principles into practice, I've been developing an open-source framework called the Research Management System ([github.com/dermot-obrien/ai-assisted-research](https://github.com/dermot-obrien/ai-assisted-research)). It assumes you're already using agentic tools like Anthropic Claude Code, Google Gemini CLI, or OpenAI Codex, and provides a structured lineage layer on top.

It's still early, but I'm using it in my own time series forecasting research, and it has already changed how I work with AI agents. Early on, I had two hypothesis strands running in parallel that were, without my realising it, testing the same underlying assumption from different angles. The lineage graph made the overlap visible before I wasted a week of compute on redundant experiments. That kind of catch is only possible when the history of *why* each experiment was started is preserved, not just the results. I'm also starting to publish that research as a series of articles, e.g. [Graph Iterated Function Systems: Adding Structure to Self-Similarity](https://www.dermot-obrien.com/graph-iterated-function-systems/).

The framework is built on a few core agent roles:

*   The Discovery Agent: Scans existing code and papers in a workspace to find the kernel idea and reconstruct the lineage of how you got where you are today.
*   The Specialist Agent: Looks at the current hypothesis map and proposes the most statistically likely next steps based on SOTA targets.
*   The Worker Agent: Takes a single hypothesis node and executes the experiments, tracking every finding and what prompted the next task.
*   The Auditor Agent: Ensures that the metric supremacy rule is followed, verifying that results aren't just noise.

### What this looks like in practice

Instead of saying "AI, help me with my research," the workflow becomes:
1.  *Initialize*: The Discovery agent maps your current fog into a clean lineage graph.
2.  *Propose*: You and the Specialist agent agree on the next avenue of exploration.
3.  *Execute:* The Worker agent runs the strand, producing a finding for every activity.
4.  *Synthesize*: The system automatically generates lineage documentation in a blog and ArXiv-style summary that explains exactly why the research succeeded or failed.

Your role shifts. You are no longer the person buried in the details of every experiment. You are the navigator who sets the course, reviews the findings, and uses your hard-won intuition to decide where to go next. The agents handle the mileage. You own the map.

## The AI-Augmented Future of Discovery

We are entering an era where the bottleneck for discovery is no longer the ability to *do* the work, but the ability to *direct* the work. The direction of travel is clear, even if the timeline is uncertain.

The researchers who will thrive are those who treat their lineage of ideas as a first-class asset: a structured history of every question asked, every failure recorded, and every metric tracked. They will be the ones who have lifted themselves out of the weeds and into the role of orchestrator, spending their time on the questions that only a human researcher can answer: Is this the right problem? Does this result *mean* something? What does my experience tell me that the data doesn't?

The logical endpoint is research that is largely agentic. We set the SOTA targets, and a swarm of agents navigates the hypothesis space, checking back in only when they hit a review gate or a fundamental theoretical shift. Whether that takes three years or ten, the prerequisite is the same: structured lineage, and a researcher who has learned to lead from the front rather than push from behind.

If your research is currently a fog, adding more AI without that structure won't clear it. It will make it a storm.

## Start Here

You don’t need a swarm of agents to start. Start with the discipline of the lineage:

1.  Map your fog: Spend 30 minutes today writing down your current hypothesis graph. What are the 2-3 main branches you’re exploring? What is the kernel idea at the root?
2.  Set a metric: For every experiment you run tomorrow, define exactly what success looks like in numbers *before* you start.
3.  Record the finding: When you finish a task, don’t just move on. Write one sentence: "We tried X, learned Y, and that prompts us to try Z."
4.  Explore the framework: If you want to see how we’re automating this with agents, check out the [AI-Assisted Research](https://github.com/dermot-obrien/ai-assisted-research) repository. It’s open-source, built for researchers who are already using AI tools such as Anthropic Claude Code, Google Gemini CLI, or OpenAI Codex CLI.

This discipline has a real cost up front. Writing down findings and mapping hypotheses takes time you’d rather spend running experiments. But the alternative is paying that cost later, with interest, when you’re three months deep and can’t remember why you abandoned a promising direction.

The infinite search space isn’t going away. But with a clear lineage, you can finally stop wandering and start discovering.

## References

[^1]: Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction*. MIT Press. (On the Exploration-Exploitation trade-off).

[^2]: Zeigarnik, B. (1927). "Das Behalten erledigter und unerledigter Handlungen" [On Finished and Unfinished Tasks]. *Psychologische Forschung*, 9, 1-85. English translation in Ellis, W. D. (Ed.) (1938). *A Source Book of Gestalt Psychology*. Kegan Paul.

[^3]: Newport, C. (2024). *Slow Productivity: The Lost Art of Accomplishment Without Burnout*. Portfolio/Penguin. (On the "overhead tax" of accumulated commitments.)

[^4]: Leroy, S. (2009). "Why Is It So Hard to Do My Work? The Challenge of Attention Residue When Switching Between Work Tasks." *Organizational Behavior and Human Decision Processes*, 109(2), 168-181.

[^5]: For readers less familiar with graph theory: a graph is a set of nodes connected by edges. A DAG (Directed Acyclic Graph) is a graph where edges only move in one direction and never loop back, making it a natural structure for representing the forward evolution of ideas.

*Dermot O'Brien is a senior AI technologist and researcher. He is the creator of the AI-Assisted Research framework, built on the [AI-Assisted Work](https://github.com/dermot-obrien/ai-assisted-work) base framework, dedicated to scaling human cognition through structured agentic workflows. The research framework is available at [github.com/dermot-obrien/ai-assisted-research](https://github.com/dermot-obrien/ai-assisted-research).*
