# Change: let the planner agent hand research to a sub-agent

A planner agent drafts a plan. The change lets it hand code research to a code-explorer sub-agent.
The sub-agent returns a findings summary. A reviewer agent then checks the plan against the summary.
The reviewer returns pass or a list of gaps. The planner revises on a gap.
The risk is what each agent passes to the next.

Actors: developer who starts the planner.

Tier: light.

Source: our own prompt.
