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
