# Feedback loop options

Try these options in order.
Select the first option that reaches the failed seam.

1. Run a failing unit, integration, or end-to-end test at the nearest useful seam.
2. Send an HTTP request to a running development server.
3. Run the CLI with a fixture and compare its output with an approved snapshot.
4. Drive the interface with Playwright or Puppeteer and check the DOM, console, and network.
5. Replay a captured request, payload, or event log through the isolated code path.
6. Run the minimum system subset that reaches the bug with one function call.
7. Run random inputs and check each result for the reported failure.
8. Automate setup and checks across known revisions for `git bisect run`.
9. Compare the same input across two versions or configurations.
10. Use a structured human-driven script only when automation cannot perform the required action.
