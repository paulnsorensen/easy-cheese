# TypeScript / JavaScript De-slop Catalog

This catalog gives per-language evidence for the `age` `deslop` dimension.
Each pattern names a TypeScript or JavaScript AI signature for review.
Most patterns map to a typescript-eslint rule, which gives a citable rule name for a finding.
Use this catalog with the `deslop` rubric in `dimensions.md`.
This catalog supplies the detail. It defines no separate severity scale.

## 1. `any` instead of a real type

When types become complex, AI gives up and uses `any`, which discards TypeScript's type safety.

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

AI mixes paradigms or uses promise chains when `async/await` provides clearer code.

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

AI adds debug logging and leaves it in the code.

```typescript
// SLOP
console.log("Fetching user...");
const user = await fetchUser(id);
console.log("User fetched:", user);
console.log("Processing...");
```

**Fix:** Delete all `console.log` debug statements. Use a proper logger when you need observability. Remove the statements when the code is self-evident.

## 4. `Array.forEach` with async callbacks

`forEach` does not await asynchronous callbacks. Those callbacks run, but their promises become unobserved.

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

// CLEAN — the `undefined` arm is unreachable under the declared type
function greet(name: string | null): string {
  return name === null ? "Hello, stranger" : `Hello, ${name}`;
}
```

Keep the null semantics. Do not replace a null check with a truth test.
A truth test also rejects `""`, `0`, `NaN`, and `false`.
Use `name ?? "stranger"` when you want null and undefined only.
Lint rule `@typescript-eslint/no-unnecessary-condition` catches a condition that always evaluates to true or false.

## 6. `JSON.parse(JSON.stringify())` for deep cloning

```typescript
// SLOP
const cloned = JSON.parse(JSON.stringify(user));

// CLEAN — when the value holds only structured-cloneable data
const cloned = structuredClone(user);
```

Check the clone requirements first.
`structuredClone` throws on a function, a class instance method, a `Symbol`, and a DOM node.
It keeps a `Date`, a `Map`, a `Set`, and a cyclic reference, which the JSON round trip loses.
Use a library deep clone when the value holds a function or a class instance.

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

## 8. Importing more names than the file uses

```typescript
// SLOP — five names where the file uses one
import { UserService, UserModel, UserDTO, UserMapper, UserValidator } from "./users";

// CLEAN — import only what you use
import { UserService } from "./users";
```

A named barrel import does not load every export by itself.
A bundler drops the unused names when three conditions hold.
The package sets `"sideEffects": false`, the modules use ECMAScript syntax, and the build runs tree shaking.
Raise this finding when one of those conditions fails, or when the file imports names it never uses.

## 9. Non-null assertion as narrowing substitute

The `!` operator suppresses compiler checks. A guard establishes a true condition for the compiler. AI-authored PRs use `!` and `as` far more often than human PRs (arXiv 2602.17955).

```typescript
// SLOP
const user = users.find(u => u.id === id)!;
processUser(user);

// CLEAN
const user = users.find(u => u.id === id);
if (!user) throw new Error(`unknown user: ${id}`);
processUser(user);
```

Lint rule `@typescript-eslint/no-non-null-assertion` detects non-null assertions.

## 10. Double assertion to force a type

The assertion `as unknown as T` lets any value claim type `T`. It bypasses the type system at the location most likely to contain an error.

```typescript
// SLOP
const config = JSON.parse(raw) as unknown as Config;

// CLEAN — validate at the boundary
const config = configSchema.parse(JSON.parse(raw)); // zod or similar
```

## 11. `@ts-ignore` instead of `@ts-expect-error`

`@ts-ignore` permanently suppresses a diagnostic. The stale directive remains after you fix the underlying error. `@ts-expect-error` fails when no diagnostic remains to suppress.

```typescript
// SLOP
// @ts-ignore
legacyCall(data);

// CLEAN
// @ts-expect-error — legacy API typed wrong upstream (issue #123)
legacyCall(data);
```

Configure the lint rule `@typescript-eslint/ban-ts-comment` with `minimumDescriptionLength`.

## 12. Floating promises

Fire-and-forget asynchronous calls can lose rejections and create accidental ordering.

```typescript
// SLOP
saveUser(user);                          // not awaited — errors disappear
items.map(async i => await process(i));  // array of dropped promises

// CLEAN
await saveUser(user);
await Promise.all(items.map(i => process(i)));

// Intentionally fire-and-forget? Handle the rejection as well:
void saveUser(user).catch((error: unknown) => logger.error({ error }));
```

`void` only marks the intent for the linter. It does not handle a rejection.
An unhandled rejection still reaches the process handler.
Attach a `.catch` to every promise that you do not await.

Relevant lint rules include `@typescript-eslint/no-floating-promises` and `@typescript-eslint/no-misused-promises`.

## 13. `enum` where a union suffices

Enums often reflect habits from other languages. Literal unions erase during compilation, serialize directly, and need no runtime object.

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

A `catch (e: any)` block can log and rethrow the error at every level. No level handles the error.

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
That rule covers a `.catch(callback)` argument only.
Cite `@typescript-eslint/no-explicit-any` for a `catch (e: any)` clause.
Set `useUnknownInCatchVariables` in `tsconfig.json` to type the clause as `unknown`.

## 15. `useEffect` for derived state (React)

AI often uses effects to compute values or chain fetches.

```typescript
// SLOP — derived state via effect
const [fullName, setFullName] = useState("");
useEffect(() => { setFullName(`${first} ${last}`); }, [first, last]);

// CLEAN — derive during render
const fullName = `${first} ${last}`;
```

No lint rule catches this pattern. `react-hooks/exhaustive-deps` does not catch it. Review it manually. See the react.dev article "You Might Not Need an Effect".

## Sources

- The typescript-eslint `strict-type-checked` configuration and rule documentation provide the source of truth for every rule named above.
- Chapter 5 of Effective TypeScript, 2nd ed. (Vanderkam, 2024), covers narrowing `any`'s scope.
- The arXiv 2602.17955 study provides an empirical AI-versus-human PR comparison of `!`/`as` overuse.
