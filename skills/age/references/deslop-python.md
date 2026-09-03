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

## 2. Manual `None` checks instead of truthiness

```python
# SLOP
if user is not None and user.name is not None and len(user.name) > 0:
    greet(user.name)

# CLEAN
if user and user.name:
    greet(user.name)
```

## 3. Old-style string formatting

AI mixes `%`, `.format()`, and f-strings inconsistently.

```python
# SLOP
message = "Hello, %s! You have %d messages." % (name, count)
message = "Hello, {}!".format(name)

# CLEAN — f-strings everywhere (Python 3.6+)
message = f"Hello, {name}! You have {count} messages."
```

## 4. Silent `except: pass`

Swallowing exceptions without handling creates the largest debugging time sink.

```python
# SLOP
try:
    risky_operation()
except Exception:
    pass  # Silent failure — good luck debugging

# CLEAN — either handle it meaningfully or don't catch it
# If you truly need to ignore: except SpecificError as e: logger.debug(...)
```

## 5. Raw dicts for structured data

AI returns `{"id": 1, "name": "Alice"}` instead of using a dataclass.
A dataclass provides type safety, IDE support, and self-documenting code.

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

## Sources

- Ruff rule docs (docs.astral.sh/ruff/rules) verify every rule code above.
- charlax/professional-programming documents error-handling anti-patterns with before-and-after exception examples.
- The Greg-style caveat uses the PTH123 dispute thread (discuss.python.org/t/106904) to calibrate the pathlib rule.
