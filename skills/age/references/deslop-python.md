# Python De-slop Catalog

This section provides Python evidence for the `age` `deslop` dimension.
Each pattern identifies a Python-specific AI tell for review.
Most patterns map to a Ruff rule code.
The rule code gives reviewers a citable name for a finding.
Use this section with the `deslop` rubric in `dimensions.md`.
This section provides review details, not a separate severity scale.

## 1. `range(len())` instead of `enumerate`

AI defaults to C-style index loops.

```python
# SLOP
for i in range(len(items)):
    print(i, items[i])

# CLEAN
for i, item in enumerate(items):
    print(i, item)
```

Iterate directly when you do not need the index:

```python
for item in items:
    process(item)
```

## 2. Redundant `None` and length checks

A truth test is not a `None` check. It also rejects `""`, `0`, `0.0`, `[]`, `{}`, and `False`.
Use it only when the empty value and the missing value need the same branch.

```python
# SLOP — three checks where the type allows one
if user is not None and user.name is not None and len(user.name) > 0:
    greet(user.name)

# CLEAN — when an empty name and a missing name take the same branch
if user and user.name:
    greet(user.name)

# CLEAN — when the branches differ, keep the explicit check
if user is not None and user.name is not None:
    greet(user.name)
```

Keep `is not None` on any value that can hold `0`, `False`, or an empty container.

## 3. Old-style string formatting

AI mixes `%`, `.format()`, and f-strings inconsistently.

```python
# SLOP
message = "Hello, %s! You have %d messages." % (name, count)
message = "Hello, {}!".format(name)

# CLEAN — f-strings for a plain string
message = f"Hello, {name}! You have {count} messages."

# CLEAN — %-style for a logging call, which formats only when the record emits
logger.info("Hello, %s! You have %d messages.", name, count)
```

Do not use an f-string in a logging call.
The f-string formats on every call, even when the level filters the record.
Ruff rule `G004` flags an f-string in a logging call.

## 4. Silent `except: pass`

An unhandled exception that the code swallows leaves no evidence.
The defect then costs the most time to find.

```python
# SLOP
try:
    risky_operation()
except Exception:
    pass  # Silent failure: no log, no trace, no evidence

# CLEAN — either handle it meaningfully or don't catch it
# If you truly need to ignore: except SpecificError as e: logger.debug(...)
```

## 5. Raw dicts for structured data

AI returns `{"id": 1, "name": "Alice"}` instead of a declared type.
A dataclass gives static types, editor support, and a named shape.
A dataclass does not check a type at run time. It assigns whatever the caller passes.
Use `pydantic` or `attrs` with validators when the data crosses a trust boundary.

```python
# SLOP
def get_user():
    return {"id": 1, "name": "Alice", "email": "alice@example.com"}

# CLEAN
@dataclass
class User:
    id: int
    name: str
    email: str
```

## 6. `open()` without context manager

```python
# SLOP
f = open("file.txt")
data = f.read()
f.close()  # Never reached if f.read() throws

# CLEAN
with open("file.txt") as f:
    data = f.read()
```

## 7. Overzealous type hints on obvious locals

```python
# SLOP
name: str = "Alice"
count: int = 0
items: list[str] = []
active: bool = True

# CLEAN — type hints on function signatures, not obvious assignments
name = "Alice"
count = 0
items: list[str] = []  # Empty collection annotation is fine (inference can't know the element type)
active = True
```

## 8. List comprehension where a generator suffices

```python
# SLOP — builds entire list in memory just to iterate
total = sum([x * x for x in range(1_000_000)])

# CLEAN — generator expression, lazy evaluation
total = sum(x * x for x in range(1_000_000))
```

## 9. Mutable default arguments

`def f(x=[])` shares one list across every call.

```python
# SLOP
def append_item(item, items=[]):
    items.append(item)
    return items

# CLEAN
def append_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

Ruff identifies this pattern with `B006`.

## 10. HTTP calls without a timeout

`requests` and `httpx` calls without `timeout=` can hang forever when the server hangs.

```python
# SLOP
response = requests.get(url)

# CLEAN
response = requests.get(url, timeout=10)
```

Ruff identifies this pattern with `S113`.

## 11. try/except shape slop

The tryceratops family covers oversized `try` blocks with logging noise.

```python
# SLOP — log-and-raise duplicates the traceback up the stack
try:
    process(item)
except ValueError as e:
    logger.error(f"failed: {e}")   # TRY400: use logger.exception
    raise

# SLOP — raise inside try, caught by its own except (TRY301);
# success path buried inside try (TRY300)
try:
    value = compute()
    if value < 0:
        raise ValueError("negative")
    return transform(value)
except ValueError:
    ...

# CLEAN — narrow try, raise outside it, else for the success path
value = compute()
if value < 0:
    raise ValueError("negative")
try:
    data = load(value)
except OSError:
    logger.exception("load failed")
    raise
else:
    return transform(data)
```

Ruff identifies this shape with `TRY300`, `TRY301`, `TRY400`, and `TRY401`.

## 12. Deprecated typing forms

Models that learn from pre-3.9 code emit `typing.List`/`Optional`/`Union`.

```python
# SLOP
from typing import Dict, List, Optional, Union
def find(ids: List[int]) -> Optional[Dict[str, Union[int, str]]]: ...

# CLEAN — builtin generics (3.9+) and | unions (3.10+)
def find(ids: list[int]) -> dict[str, int | str] | None: ...
```

Ruff identifies this pattern with `UP006`, `UP007`, and `UP045`.

## 13. os.path / pathlib mixing

A module interleaves `os.path.join`, `os.path.exists`, and `Path`.

```python
# SLOP
path = os.path.join(base, "config.yaml")
if os.path.exists(path): ...

# CLEAN
path = Path(base) / "config.yaml"
if path.exists(): ...
```

Ruff uses the `PTH` family for this pattern.
`open(path)` on a `Path` is valid.
Core developers contest the `PTH123` rule, which forces `Path.open()`.
Do not fix `open(path)` on a `Path` solely to satisfy `PTH123`.

## 14. print() debugging in library code

```python
# SLOP
print(f"processing {item}")

# CLEAN — logging, or delete if the code is self-evident
logger.debug("processing %s", item)
```

## 15. Non-exhaustive `match` over a closed union

AI writes a `match` or `if/elif` chain over an enum or `Literal` union and leaves a silent `case _:` or no final branch.
A new member then falls through without a type error.
`assert_never` turns the missing case into a mypy or pyright error, so the checker carries that review.
No Ruff rule covers this. Review it by hand.

```python
# SLOP
match status:
    case Status.ACTIVE:
        return activate()
    case Status.INACTIVE:
        return deactivate()
    case _:
        pass

# CLEAN
match status:
    case Status.ACTIVE:
        return activate()
    case Status.INACTIVE:
        return deactivate()
    case _:
        assert_never(status)
```

## Sources

- Ruff rule docs (docs.astral.sh/ruff/rules) verify every rule code above.
- `typing.assert_never` (Python 3.11+, `typing_extensions` before) documents the exhaustiveness idiom; mypy and pyright both report the unreachable-argument error.
- charlax/professional-programming documents error-handling anti-patterns with before-and-after exception examples.
- The `pathlib` rule follows the PTH123 dispute thread (discuss.python.org/t/106904).
