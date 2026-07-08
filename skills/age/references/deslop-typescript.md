# TypeScript / JavaScript De-slop Catalog

Per-language evidence for the `age` `deslop` dimension. Each pattern is a TS/JS-specific AI tell to look for during review; most map to a typescript-eslint rule, giving a citable rule name to attach to a finding. Use alongside `dimensions.md`'s `deslop` rubric — this is the "Look for" detail, not a separate severity scale.

## 1. `any` as escape hatch

When types get complex, AI gives up and uses `any`, throwing away
everything TypeScript provides.

```typescript
// SLOP
function processData(data: any): any {
  return data.value;
}

// CLEAN
function processData<T extends { value: unknown }>(data: T): T['value'] {
  return data.value;
}

// Or if you genuinely don't know the shape:
function processData(data: unknown): unknown {
  if (hasValue(data)) return data.value;
  throw new Error("missing value field");
}
```

## 2. `.then()` chains instead of `async/await`

AI mixes paradigms or uses promise chains where async/await is cleaner.

```typescript
// SLOP
function fetchUser(id: string) {
  return fetch(`/api/users/${id}`)
    .then(res => res.json())
    .then(data => data.user)
    .catch(err => console.error(err));
}

// CLEAN
async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  return (await res.json()).user;
  // Let errors propagate — the caller should decide what to do
}
```

## 3. `console.log` debugging left in

AI adds debug logging that never gets removed.

```typescript
// SLOP
console.log("Fetching user...");
const user = await fetchUser(id);
console.log("User fetched:", user);
console.log("Processing...");
```

**Fix:** Delete all `console.log` debug statements. Use a proper logger
if observability is needed, or remove entirely if the code is
self-evident.

## 4. `Array.forEach` with async callbacks

`forEach` doesn't await — async callbacks fire and are silently dropped.

```typescript
// SLOP — these await calls do nothing useful
items.forEach(async (item) => {
  await processItem(item);  // Runs concurrently, forEach doesn't wait
});

// CLEAN — sequential
for (const item of items) {
  await processItem(item);
}

// CLEAN — concurrent with control
await Promise.all(items.map(item => processItem(item)));
```

## 5. Redundant null checks TypeScript already handles

With `strictNullChecks`, the compiler enforces null safety.

```typescript
// SLOP — name can't be undefined here, the type says string | null
function greet(name: string | null): string {
  if (name === null || name === undefined) {
    return "Hello, stranger";
  }
  return `Hello, ${name}`;
}

// CLEAN
function greet(name: string | null): string {
  return name ? `Hello, ${name}` : "Hello, stranger";
}
```

Lint: `@typescript-eslint/no-unnecessary-condition` — catches provably
true/false conditions in general, not just null checks.

## 6. `JSON.parse(JSON.stringify())` for deep cloning

```typescript
// SLOP
const cloned = JSON.parse(JSON.stringify(user));

// CLEAN — structuredClone (available in all modern runtimes)
const cloned = structuredClone(user);
```

## 7. Redundant type annotations on initialized variables

```typescript
// SLOP
const count: number = 0;
const name: string = user.name;
const isActive: boolean = true;
const users: User[] = getUsers();

// CLEAN — inference handles these
const count = 0;
const name = user.name;
const isActive = true;
const users = getUsers();  // Return type already typed

// Keep annotations on empty collections or ambiguous initializers
const users: User[] = [];
```

## 8. Over-importing from barrel files

```typescript
// SLOP — grabs everything, bloats bundle
import { UserService, UserModel, UserDTO, UserMapper, UserValidator } from "./users";

// CLEAN — import only what you use
import { UserService } from "./users";
```

## 9. Non-null assertion as narrowing substitute

`!` tells the compiler to shut up; a guard tells it something true. AI-authored
PRs use `!` and `as` at a much higher rate than human PRs (arXiv 2602.17955).

```typescript
// SLOP
const user = users.find(u => u.id === id)!;
processUser(user);

// CLEAN
const user = users.find(u => u.id === id);
if (!user) throw new Error(`unknown user: ${id}`);
processUser(user);
```

Lint: `@typescript-eslint/no-non-null-assertion`.

## 10. Double assertion to force a type

`as unknown as T` makes any value claim any type — it erases the type system
at exactly the spot most likely to be wrong.

```typescript
// SLOP
const config = JSON.parse(raw) as unknown as Config;

// CLEAN — validate at the boundary
const config = configSchema.parse(JSON.parse(raw)); // zod or similar
```

## 11. `@ts-ignore` instead of `@ts-expect-error`

`@ts-ignore` silences forever — when the underlying error is fixed, the stale
directive stays. `@ts-expect-error` fails when it no longer suppresses anything.

```typescript
// SLOP
// @ts-ignore
legacyCall(data);

// CLEAN
// @ts-expect-error — legacy API typed wrong upstream (issue #123)
legacyCall(data);
```

Lint: `@typescript-eslint/ban-ts-comment` (set `minimumDescriptionLength`).

## 12. Floating promises

Fire-and-forget async calls — rejections vanish, ordering is accidental.

```typescript
// SLOP
saveUser(user);                          // not awaited — errors disappear
items.map(async i => await process(i));  // array of dropped promises

// CLEAN
await saveUser(user);
await Promise.all(items.map(i => process(i)));

// Intentionally fire-and-forget? Say so:
void saveUser(user);
```

Lint: `@typescript-eslint/no-floating-promises`, `@typescript-eslint/no-misused-promises`.

## 13. `enum` where a union suffices

Enums imported from other languages' habits. Literal unions are erasable,
serializable, and need no runtime object.

```typescript
// SLOP
enum Status { Active = "active", Inactive = "inactive" }

// CLEAN
type Status = "active" | "inactive";

// When you need the values at runtime:
const STATUSES = ["active", "inactive"] as const;
type Status = (typeof STATUSES)[number];
```

## 14. Catch-block slop

`catch (e: any)` plus log-and-rethrow: the error is logged at every level and
handled at none.

```typescript
// SLOP
try {
  await handler(req);
} catch (e: any) {
  console.error(e);
  throw e;
}

// CLEAN — catch only where you add value; the error is unknown, not any
try {
  await handler(req);
} catch (e) {
  if (e instanceof ValidationError) return res.status(400).json(e.detail);
  throw e; // the boundary logger handles the rest
}
```

Lint: `@typescript-eslint/only-throw-error`,
`@typescript-eslint/use-unknown-in-catch-callback-variable`.

## 15. `useEffect` for derived state (React)

Effects reached for to compute values or chain fetches.

```typescript
// SLOP — derived state via effect
const [fullName, setFullName] = useState("");
useEffect(() => { setFullName(`${first} ${last}`); }, [first, last]);

// CLEAN — derive during render
const fullName = `${first} ${last}`;
```

No lint catches this (`react-hooks/exhaustive-deps` doesn't) — review by hand.
See react.dev "You Might Not Need an Effect".

## Sources

- typescript-eslint `strict-type-checked` config + rule docs — ground truth for every rule named above
- Effective TypeScript, 2nd ed. (Vanderkam, 2024) — ch. 5 on narrowing `any`'s scope
- arXiv 2602.17955 — empirical AI-vs-human PR comparison (`!`/`as` overuse)
