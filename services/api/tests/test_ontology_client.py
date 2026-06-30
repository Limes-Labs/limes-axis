from axis_api.ontology.client import normalize_query_answer


class DocumentAnswer:
    def is_concept_documents(self) -> bool:
        return True

    def as_concept_documents(self):
        return iter(
            [
                {
                    "kind": "node",
                    "node_id": "typedb_asset_line_7",
                    "label": "Line 7",
                },
                None,
            ]
        )


class ValueConcept:
    def __init__(self, value: object) -> None:
        self.value = value

    def is_value(self) -> bool:
        return True

    def as_value(self) -> "ValueConcept":
        return self

    def get(self) -> object:
        return self.value


class AttributeConcept:
    def __init__(self, value: object) -> None:
        self.value = value

    def is_value(self) -> bool:
        return False

    def is_attribute(self) -> bool:
        return True

    def as_attribute(self) -> "AttributeConcept":
        return self

    def get_value(self) -> object:
        return self.value


class EntityType:
    def get_label(self) -> str:
        return "asset"


class EntityConcept:
    def is_value(self) -> bool:
        return False

    def is_attribute(self) -> bool:
        return False

    def is_entity(self) -> bool:
        return True

    def get_iid(self) -> str:
        return "0x123"

    def get_type(self) -> EntityType:
        return EntityType()


class ConceptRow:
    def column_names(self):
        return ["axis_id", "label", "entity"]

    def get(self, column_name: str) -> object:
        return {
            "axis_id": ValueConcept("typedb_asset_line_7"),
            "label": AttributeConcept("Line 7"),
            "entity": EntityConcept(),
        }[column_name]


class RowAnswer:
    def is_concept_documents(self) -> bool:
        return False

    def is_concept_rows(self) -> bool:
        return True

    def as_concept_rows(self):
        return iter([ConceptRow()])


def test_normalize_query_answer_returns_concept_documents_as_dicts() -> None:
    assert normalize_query_answer(DocumentAnswer()) == [
        {
            "kind": "node",
            "node_id": "typedb_asset_line_7",
            "label": "Line 7",
        }
    ]


def test_normalize_query_answer_maps_concept_rows_to_public_values() -> None:
    assert normalize_query_answer(RowAnswer()) == [
        {
            "axis_id": "typedb_asset_line_7",
            "label": "Line 7",
            "entity": {
                "iid": "0x123",
                "type": "asset",
            },
        }
    ]
