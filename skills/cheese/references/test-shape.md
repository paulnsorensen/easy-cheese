# Test shape

Cook and Press follow these rules when they write tests.
Each rule removes one source of redundant or oversized suites.
A new test must catch a defect that no existing test catches.

## Placement

- Extend the existing test file for the module under test.
- Do not create a second file for the same seam, such as `test_press_<module>.py` beside `test_<module>.py`.
- Put a new test next to the tests for the same contract.
- Name the test for the contract that it checks, not for the attack or the phase that wrote it.
- Put each acceptance marker on one test only. Do not copy a marker that an existing test carries.

## Overlap

Before you add a test, find the existing test closest to it.
The closest test calls the same function and reaches the same branch.

- When an existing test asserts the same seam and branch, do not add the test.
- Otherwise, name the branch, input class, or false success that only the new test catches.

## Tables

- Write one row for each equivalence class or validator branch, not one row for each value.
- Give each row an id that names its class, such as `pytest.param("nan", id="non-finite")`.
- Keep a table at 8 rows or fewer. Above 8 rows, record the reason for each extra class.
- Stack two tables only when each axis selects a different branch.
- Otherwise, write one table of the combinations that matter. The 8-row cap applies to the product.

```python
# Weak: 13 rows that reach 4 branches.
@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "1e999", "2", "1.01", "-0.01",
                                 "true", "null", "[1]", '"1"', "", "{"])

# Strong: one row for each branch.
@pytest.mark.parametrize("raw", [
    pytest.param("nan", id="non-finite"),
    pytest.param("1.01", id="above-range"),
    pytest.param("true", id="not-a-number"),
    pytest.param("{", id="not-json"),
])
```

## Generated inputs

- Check an invariant over many inputs with one property test.
- In Python, use Hypothesis with a fixed `max_examples` and `derandomize=True`.
- In another language, use its property-test library with a fixed seed.
- A small seeded loop inside one test is also correct.
- Do not write `parametrize("trial", range(N))`. Each trial becomes one more test case and reaches no new branch.
- Before you add a property, make sure that no existing property test checks the same invariant.

## Scope

Test the project code.
Do not add rows that differ only in how the standard library, the language runtime, or a dependency treats a value.
For example, rows for `sys.exit(256)`, `sys.exit(True)`, and `sys.exit(2.5)` test CPython, not code that passes an exit code through.

## Seams

- Use the cheapest seam that proves the claim. Try a direct call first, then an in-process integration.
- Start a subprocess, a fresh interpreter, a container, or a sandbox only when the process boundary is the contract.
- Do not start a process for each table row. Keep one process test, and test the other classes through a direct call.
- Prove a size limit with an input just above the limit, not with a large allocation.
