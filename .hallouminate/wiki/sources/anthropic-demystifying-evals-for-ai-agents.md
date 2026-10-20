# Demystifying evals for AI agents

Anthropic's engineering article, last verified 2026-10-17, supports the claim that agent evaluation should grade the final environment outcome with bypass-resistant graders, positive and negative cases, a known working reference solution, and isolated repeated trials.
Canonical source: [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

## Outcome over transcript

The Anthropic evals article defines the outcome as "the final state in the environment at the end of the trial" (source L35). It says "it's often better to grade what the agent produced, not the path it took" (L258).

## Grader design rules

- "For each task, it's useful to create a reference solution: a known working output that passes all graders" (L245).
- "Test both the cases where a behavior should occur and where it shouldn't" (L247).
- "Each trial should be 'isolated' by starting from a clean environment" (L253).
- "Make your graders resistant to bypasses or hacks" (L265).
- A failed task's transcript shows whether the agent made a mistake or the grader "rejected a valid solution" (L270).

## Repeated trials and eval saturation

The article runs multiple trials because model outputs vary between runs (L32). It separates capability evals ("What can this agent do well?") from regression evals ("Does the agent still handle all the tasks it used to?") (L123-124). "An eval at 100% tracks regressions but provides no signal for improvement" (L274). Evals also need maintenance and "can create false confidence if it doesn't match real usage patterns" (L305-306).

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents · Updated: 2026-10-18_
