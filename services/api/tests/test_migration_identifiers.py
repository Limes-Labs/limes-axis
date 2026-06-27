from __future__ import annotations

import ast
from pathlib import Path

POSTGRES_IDENTIFIER_LIMIT = 63
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


class MigrationIdentifierVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.string_assignments: dict[str, str] = {}
        self.string_tuple_assignments: dict[str, tuple[str, ...]] = {}
        self.loop_values: dict[str, tuple[str, ...]] = {}
        self.identifiers: list[tuple[int, str]] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            self.generic_visit(node)
            return

        name = node.targets[0].id
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self.string_assignments[name] = node.value.value
        tuple_values = self._string_tuple(node.value)
        if tuple_values is not None:
            self.string_tuple_assignments[name] = tuple_values
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return

        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self.string_assignments[node.target.id] = node.value.value
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        if isinstance(node.target, ast.Name):
            values = self._string_tuple(node.iter)
            if values is None and isinstance(node.iter, ast.Name):
                values = self.string_tuple_assignments.get(node.iter.id)
            if values is not None:
                previous = self.loop_values.get(node.target.id)
                self.loop_values[node.target.id] = values
                for child in node.body:
                    self.visit(child)
                if previous is None:
                    self.loop_values.pop(node.target.id, None)
                else:
                    self.loop_values[node.target.id] = previous
                for child in node.orelse:
                    self.visit(child)
                return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_create_or_drop_index_call(node) and node.args:
            self._record_expression(node.args[0], node.lineno)

        for keyword in node.keywords:
            if keyword.arg == "name":
                self._record_expression(keyword.value, node.lineno)
        self.generic_visit(node)

    def _record_expression(self, node: ast.AST, lineno: int) -> None:
        for value in self._evaluate_identifier_expression(node):
            self.identifiers.append((lineno, value))

    def _evaluate_identifier_expression(self, node: ast.AST) -> tuple[str, ...]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return (node.value,)
        if isinstance(node, ast.Name):
            loop_values = self.loop_values.get(node.id)
            if loop_values is not None:
                return loop_values
            value = self.string_assignments.get(node.id)
            return (value,) if value is not None else ()
        if isinstance(node, ast.JoinedStr):
            return self._evaluate_joined_string(node)
        return ()

    def _evaluate_joined_string(self, node: ast.JoinedStr) -> tuple[str, ...]:
        partials = [""]
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                partials = [partial + part.value for partial in partials]
                continue
            if isinstance(part, ast.FormattedValue):
                values = self._evaluate_identifier_expression(part.value)
                if not values:
                    return ()
                partials = [partial + value for partial in partials for value in values]
                continue
            return ()
        return tuple(partials)

    def _string_tuple(self, node: ast.AST) -> tuple[str, ...] | None:
        if not isinstance(node, ast.Tuple):
            return None
        values: list[str] = []
        for element in node.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                return None
            values.append(element.value)
        return tuple(values)

    def _is_create_or_drop_index_call(self, node: ast.Call) -> bool:
        if not isinstance(node.func, ast.Attribute):
            return False
        if node.func.attr not in {"create_index", "drop_index"}:
            return False
        return isinstance(node.func.value, ast.Name) and node.func.value.id == "op"


def test_migration_database_identifiers_fit_postgres_limit() -> None:
    failures: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = MigrationIdentifierVisitor(path)
        visitor.visit(tree)
        for lineno, identifier in visitor.identifiers:
            if len(identifier) > POSTGRES_IDENTIFIER_LIMIT:
                failures.append(
                    f"{path.name}:{lineno} {len(identifier)} chars: {identifier}"
                )

    assert failures == []
