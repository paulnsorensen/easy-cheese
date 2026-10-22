# Session state: Shape round 1 done

Tier: light.

Goal: The shop builds PDF reports outside the web request, so large accounts stop timing out.

Actors: account owner, on-call engineer.

## Evidence

- ev-1 (certain, incident 88): Reports for accounts with 50k orders time out at 30 seconds in the web app.
- ev-2 (certain, ops notes): The web app runs on three nodes in one region.

## Acceptance so far

- AC-1: A report for an account with 50k orders finishes without a web request timeout.
- AC-2: A failed report build does not take the web app down.

## Forks for round 2

- F-1: Which parts make up the report path? A: a separate report service with its own worker. B: a worker inside the web app. C: a database job. The branches differ in containers.
- F-2: How is the report service built inside? A: one controller over a builder and a renderer. B: a pipeline of three stages. C: one module. The branches differ in components inside one container.
- F-3: Where does the report worker run? A: on its own nodes. B: on the web app nodes. C: as a serverless job. The branches differ in nodes and regions.
- F-4: Which date does the team want the first report to ship? A: this quarter. B: next quarter. C: no date.

Source: our own prompt.
