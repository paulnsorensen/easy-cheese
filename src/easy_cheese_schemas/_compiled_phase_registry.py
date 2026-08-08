"""Generated phase registry data; edit skills/*/phase-contract.yaml instead."""

from __future__ import annotations

PHASE_REGISTRY_DATA = [
    {
        "contract_version": {
            "major": "1",
            "minor": "0",
            "schema_uri": "https://schemas.easy-cheese.dev/phase-contract"
        },
        "input_schema_uris": [
            "https://schemas.easy-cheese.dev/curd-result"
        ],
        "outputs": [
            {
                "destination": "cure",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-plan"
            }
        ],
        "source": "age"
    },
    {
        "contract_version": {
            "major": "1",
            "minor": "0",
            "schema_uri": "https://schemas.easy-cheese.dev/phase-contract"
        },
        "input_schema_uris": [
            "https://schemas.easy-cheese.dev/curd-plan"
        ],
        "outputs": [
            {
                "destination": "age",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-result"
            },
            {
                "destination": "cook",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-plan"
            },
            {
                "destination": "mold",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/planner-request"
            },
            {
                "destination": "press",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-result"
            }
        ],
        "source": "cook"
    },
    {
        "contract_version": {
            "major": "1",
            "minor": "0",
            "schema_uri": "https://schemas.easy-cheese.dev/phase-contract"
        },
        "input_schema_uris": [
            "https://schemas.easy-cheese.dev/curd-plan"
        ],
        "outputs": [
            {
                "destination": "age",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-result"
            }
        ],
        "source": "cure"
    },
    {
        "contract_version": {
            "major": "1",
            "minor": "0",
            "schema_uri": "https://schemas.easy-cheese.dev/phase-contract"
        },
        "input_schema_uris": [
            "https://schemas.easy-cheese.dev/planner-request"
        ],
        "outputs": [
            {
                "destination": "cook",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-plan"
            }
        ],
        "source": "mold"
    },
    {
        "contract_version": {
            "major": "1",
            "minor": "0",
            "schema_uri": "https://schemas.easy-cheese.dev/phase-contract"
        },
        "input_schema_uris": [
            "https://schemas.easy-cheese.dev/curd-result"
        ],
        "outputs": [
            {
                "destination": "age",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-result"
            }
        ],
        "source": "press"
    }
]

PHASE_REGISTRY_JSON = '{"phases":[{"contract_version":{"major":"1","minor":"0","schema_uri":"https://schemas.easy-cheese.dev/phase-contract"},"input_schema_uris":["https://schemas.easy-cheese.dev/curd-result"],"outputs":[{"destination":"cure","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-plan"}],"source":"age"},{"contract_version":{"major":"1","minor":"0","schema_uri":"https://schemas.easy-cheese.dev/phase-contract"},"input_schema_uris":["https://schemas.easy-cheese.dev/curd-plan"],"outputs":[{"destination":"age","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-result"},{"destination":"cook","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-plan"},{"destination":"mold","payload_schema_uri":"https://schemas.easy-cheese.dev/planner-request"},{"destination":"press","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-result"}],"source":"cook"},{"contract_version":{"major":"1","minor":"0","schema_uri":"https://schemas.easy-cheese.dev/phase-contract"},"input_schema_uris":["https://schemas.easy-cheese.dev/curd-plan"],"outputs":[{"destination":"age","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-result"}],"source":"cure"},{"contract_version":{"major":"1","minor":"0","schema_uri":"https://schemas.easy-cheese.dev/phase-contract"},"input_schema_uris":["https://schemas.easy-cheese.dev/planner-request"],"outputs":[{"destination":"cook","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-plan"}],"source":"mold"},{"contract_version":{"major":"1","minor":"0","schema_uri":"https://schemas.easy-cheese.dev/phase-contract"},"input_schema_uris":["https://schemas.easy-cheese.dev/curd-result"],"outputs":[{"destination":"age","payload_schema_uri":"https://schemas.easy-cheese.dev/curd-result"}],"source":"press"}]}'
