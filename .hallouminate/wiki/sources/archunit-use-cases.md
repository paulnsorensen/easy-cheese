# ArchUnit Use Cases

The ArchUnit project's official documentation page, last verified 2026-10-17, supports the claim that architecture rules for package dependencies, layers, and cycles can run as executable tests.
Canonical source: [ArchUnit Use Cases](https://www.archunit.org/use-cases)

## Executable architecture rules

The ArchUnit use cases page shows three rule kinds in Java:

```java
// Package dependency check
noClasses().that().resideInAPackage("..source..")
    .should().dependOnClassesThat().resideInAPackage("..foo..")

// Layer check
layeredArchitecture()
    .consideringAllDependencies()
    .layer("Controller").definedBy("..controller..")
    .layer("Service").definedBy("..service..")
    .whereLayer("Controller").mayNotBeAccessedByAnyLayer()
    .whereLayer("Service").mayOnlyBeAccessedByLayers("Controller")

// Cycle check
slices().matching("com.myapp.(*)..").should().beFreeOfCycles()
```

## How easy-cheese research applies it

Architecture constraints can be hard pass/fail gates beside behavior gates. A quality score must not compensate for a failed architecture rule. In Python, an equivalent check can assert the rule that `shared/` code must not import `cli/` (see `AGENTS.md` § Skill Python bundle doctrine).

## Limits of the ArchUnit evidence

ArchUnit is a Java example, not a stack recommendation. These are code excerpts, not a full page capture.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://www.archunit.org/use-cases · Updated: 2026-10-18_
