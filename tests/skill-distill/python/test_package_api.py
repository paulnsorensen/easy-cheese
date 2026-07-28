import skill_distill


def test_package_exports_the_distillation_rewrite_api() -> None:
    expected = {
        "AnnotationV1",
        "BehaviorGate",
        "DatasetV1",
        "DependencyInventoryV1",
        "DistillationRun",
        "Encoder",
        "FamilyValidation",
        "InteractionResult",
        "MemberValidation",
        "MutationCase",
        "PairEvidenceV1",
        "RepresentationCandidate",
        "RepresentationChoice",
        "ScenarioBehavior",
        "TransactionResult",
        "apply_family",
        "bisect_interaction",
        "build_tokenizer_identity",
        "choose_representation",
        "deterministic_mutations",
        "evaluate_behavior",
        "gate_interactions",
        "loaded_tokens",
        "measure_load_events",
        "select_representation",
        "token_savings",
        "validate_family",
    }

    assert set(skill_distill.__all__) == expected
    assert all(hasattr(skill_distill, name) for name in expected)
    assert skill_distill.select_representation is skill_distill.choose_representation


def test_barrel_exports_resolve_to_their_owning_modules() -> None:
    owners = {
        "apply_family": skill_distill.transaction,
        "bisect_interaction": skill_distill.interaction,
        "build_tokenizer_identity": skill_distill.tokens,
        "deterministic_mutations": skill_distill.mutations,
        "evaluate_behavior": skill_distill.behavior,
        "gate_interactions": skill_distill.interaction,
        "measure_load_events": skill_distill.tokens,
        "validate_family": skill_distill.canonical,
    }

    assert all(
        getattr(skill_distill, name) is getattr(module, name)
        for name, module in owners.items()
    )
