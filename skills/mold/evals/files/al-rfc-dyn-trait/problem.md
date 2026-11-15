# Problem: trait objects look like plain types

In the language, a trait name can stand alone as a type. That form means a trait object, which uses dynamic dispatch. It reads the same as a concrete type.

Learners confuse the two. Reviewers cannot see the cost of dynamic dispatch at the use site. The bare form also blocks the language team from giving the bare trait name another meaning later.

Existing code uses the bare form widely. A change must not break that code in one step.

## Recorded user decisions

The user made these choices in an earlier dialogue round. They are not agent decisions.

- D-1 (user): a short prefix keyword marks each trait object type. The user rejected a keyword that looks like an object word, because it implies a different language model. The user rejected a keyword from another language, because it implies that language's cost model. The user rejected a wrapper type, because it hides that the form is built in.
- D-2 (user): a warning lint with an automatic fix comes first. The bare form becomes an error only at the next edition boundary.
- Open (no user decision yet): whether the lint warns by default in the current edition, or only when a crate opts in.

Actors: language learner, library author, language team.

Tier: full.

Source: <https://github.com/rust-lang/rfcs/blob/master/text/2113-dyn-trait-syntax.md>. The upstream text is treated as Apache-2.0, and the MIT half of the dual license is unconfirmed. This fixture is our own paraphrase and copies no sentence.
