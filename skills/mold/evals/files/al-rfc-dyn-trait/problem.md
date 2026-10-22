# Problem: trait objects look like plain types

In the language, a trait name can stand alone as a type. That form means a trait object, which uses dynamic dispatch. It reads the same as a concrete type.

Learners confuse the two. Reviewers cannot see the cost of dynamic dispatch at the use site. The bare form also blocks the language team from giving the bare trait name another meaning later.

Existing code uses the bare form widely. A change must not break that code in one step.

Actors: language learner, library author, language team.

Tier: full.

Source: <https://github.com/rust-lang/rfcs/blob/master/text/2113-dyn-trait-syntax.md>. The upstream text is treated as Apache-2.0, and the MIT half of the dual license is unconfirmed. This fixture is our own paraphrase and copies no sentence.
