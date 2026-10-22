# Problem: boilerplate in data-holding classes

Many classes in Python only hold data. Each one repeats the same constructor, text form, and comparison methods by hand.

Application developers lose time and make typos. Authors of type checkers want the field list to come from the type annotations, with no plugin.

The change must add no new syntax and must not need a metaclass. A class must stay a normal class, so that it can add its own methods and inherit from other classes.

Existing options are a tuple-based factory in the standard library and a third-party package.

Actors: application developer, type checker author, standard library maintainer.

Tier: light.

Source: <https://github.com/python/peps/blob/main/peps/pep-0557.rst>. The upstream text is public domain. This fixture is our own paraphrase and copies no sentence.
