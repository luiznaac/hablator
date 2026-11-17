"""Rung 0: the pure core may use the OTel API but never the SDK or instrumentation.

import-linter rejects subpackages of external packages as forbidden modules, so
this clause is enforced statically here instead of in the layer contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

USECASE_ROOT = Path(__file__).parents[2] / "src" / "hablator" / "usecase"
FORBIDDEN_PREFIXES = (
    "opentelemetry.sdk",
    "opentelemetry.exporter",
    "opentelemetry.instrumentation",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_usecase_imports_no_otel_sdk_exporter_or_instrumentation() -> None:
    offenders: list[str] = []
    for path in USECASE_ROOT.rglob("*.py"):
        for module in _imported_modules(path):
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_PREFIXES):
                offenders.append(f"{path.relative_to(USECASE_ROOT)}: {module}")
    assert offenders == []


SLICE_ORDER = ("delivery", "notification", "channel")
_ALLOWED_SLICE_IMPORTS: dict[str, set[str]] = {
    "delivery": {"delivery", "notification", "channel"},
    "notification": {"notification", "channel"},
    "channel": {"channel"},
}


def _module_name(path: Path, usecase_root: Path) -> str:
    parts = path.relative_to(usecase_root).with_suffix("").parts
    return ".".join(("hablator", "usecase", *parts))


def _resolved_imports(path: Path, module_name: str) -> set[str]:
    """Every module an AST node imports, with relative imports resolved to dotted names."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = module_name.split(".")[:-1]
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                modules.add(".".join((*base, node.module)) if node.module else ".".join(base))
            elif node.module:
                modules.add(node.module)
    return modules


def _slice_of(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 3 or parts[:2] != ["hablator", "usecase"]:
        return None
    return parts[2] if parts[2] in SLICE_ORDER else None


def slice_violations(usecase_root: Path) -> list[str]:
    """Return every import that points up the `delivery -> notification -> channel` DAG."""
    violations: list[str] = []
    for path in usecase_root.rglob("*.py"):
        module_name = _module_name(path, usecase_root)
        source_slice = _slice_of(module_name)
        if source_slice is None:
            continue
        for imported in _resolved_imports(path, module_name):
            target_slice = _slice_of(imported)
            if target_slice is None or target_slice in _ALLOWED_SLICE_IMPORTS[source_slice]:
                continue
            violations.append(f"{module_name} imports {imported} ({source_slice} -> {target_slice})")
    return violations


def test_usecase_slices_follow_the_dag() -> None:
    assert slice_violations(USECASE_ROOT) == []


def test_slice_dag_checker_flags_a_violation(tmp_path: Path) -> None:
    channel = tmp_path / "channel"
    notification = tmp_path / "notification"
    channel.mkdir()
    notification.mkdir()
    (notification / "__init__.py").write_text("", encoding="utf-8")
    (channel / "__init__.py").write_text("", encoding="utf-8")
    (channel / "provider.py").write_text(
        "from hablator.usecase.notification.model import Delivery\n",
        encoding="utf-8",
    )

    violations = slice_violations(tmp_path)

    assert violations == [
        "hablator.usecase.channel.provider imports hablator.usecase.notification.model (channel -> notification)"
    ]
