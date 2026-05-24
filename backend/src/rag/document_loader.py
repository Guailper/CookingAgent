"""Load local recipe files into plain RAG documents."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from src.rag.indexing_service import RagDocument

SUPPORTED_RAG_DATA_EXTENSIONS = frozenset({".md", ".markdown", ".txt", ".json", ".jsonl", ".csv"})
TEXT_RAG_DATA_EXTENSIONS = frozenset({".md", ".markdown", ".txt"})

TITLE_FIELDS = ("title", "name", "recipe_name", "菜名", "名称")
INGREDIENT_FIELDS = ("ingredients", "ingredient", "食材", "原料")
SEASONING_FIELDS = ("seasonings", "seasoning", "调料", "调味料")
STEP_FIELDS = ("steps", "directions", "instructions", "做法", "步骤")
TIP_FIELDS = ("tips", "notes", "小贴士", "备注")


@dataclass(frozen=True)
class LoadedRecipeRecord:
    """One structured recipe record extracted from JSON/JSONL/CSV."""

    title: str
    text: str
    metadata: dict[str, Any]


def iter_supported_files(data_dir: Path) -> list[Path]:
    """Return local RAG files in a deterministic order."""

    return sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_RAG_DATA_EXTENSIONS
    )


def load_rag_documents_from_path(
    path: Path,
    data_dir: Path,
    knowledge_base_id: str,
) -> list[RagDocument]:
    """Load one supported local file as one or more RAG documents."""

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_RAG_DATA_EXTENSIONS:
        return []

    if suffix in TEXT_RAG_DATA_EXTENSIONS:
        return [_load_text_document(path, data_dir, knowledge_base_id)]

    records = _load_structured_records(path)
    return [
        RagDocument(
            knowledge_base_public_id=knowledge_base_id,
            document_public_id=build_document_id(path.relative_to(data_dir), record_index=index),
            title=record.title,
            text=record.text,
            metadata={
                **_build_base_metadata(path, data_dir, document_format=suffix.lstrip(".")),
                **record.metadata,
                "source_record_index": index,
            },
        )
        for index, record in enumerate(records)
        if record.text.strip()
    ]


def build_document_id(relative_path: Path, record_index: int | None = None) -> str:
    """Build stable document ids so rebuilds do not depend on local absolute paths."""

    payload = relative_path.as_posix()
    if record_index is not None:
        payload = f"{payload}#{record_index}"

    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:20]
    return f"doc_{digest}"


def _load_text_document(path: Path, data_dir: Path, knowledge_base_id: str) -> RagDocument:
    relative_path = path.relative_to(data_dir)
    text = path.read_text(encoding="utf-8")

    return RagDocument(
        knowledge_base_public_id=knowledge_base_id,
        document_public_id=build_document_id(relative_path),
        title=_extract_title_from_text(text) or path.stem,
        text=text,
        metadata=_build_base_metadata(path, data_dir, document_format=path.suffix.lower().lstrip(".")),
    )


def _load_structured_records(path: Path) -> list[LoadedRecipeRecord]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _records_from_json(path)
    if suffix == ".jsonl":
        return _records_from_jsonl(path)
    if suffix == ".csv":
        return _records_from_csv(path)
    return []


def _records_from_json(path: Path) -> list[LoadedRecipeRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("recipes"), list):
        raw_records = data["recipes"]
    elif isinstance(data, list):
        raw_records = data
    else:
        raw_records = [data]

    return _coerce_records(raw_records, fallback_title=path.stem)


def _records_from_jsonl(path: Path) -> list[LoadedRecipeRecord]:
    raw_records: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            raw_records.append(json.loads(stripped))

    return _coerce_records(raw_records, fallback_title=path.stem)


def _records_from_csv(path: Path) -> list[LoadedRecipeRecord]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return _coerce_records(list(reader), fallback_title=path.stem)


def _coerce_records(raw_records: Iterable[Any], fallback_title: str) -> list[LoadedRecipeRecord]:
    records: list[LoadedRecipeRecord] = []
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            continue

        title = _first_text(raw_record, TITLE_FIELDS) or f"{fallback_title}-{index + 1}"
        text = _render_recipe_text(raw_record, title)
        records.append(
            LoadedRecipeRecord(
                title=title,
                text=text,
                metadata={
                    "recipe_name": title,
                    "source_record_fields": sorted(str(key) for key in raw_record),
                },
            )
        )

    return records


def _render_recipe_text(record: dict[str, Any], title: str) -> str:
    sections = [f"# {title}"]

    overview_lines = _render_overview_lines(record)
    if overview_lines:
        sections.append("## 概览\n" + "\n".join(overview_lines))

    _append_list_section(sections, "食材", _first_value(record, INGREDIENT_FIELDS))
    _append_list_section(sections, "调料", _first_value(record, SEASONING_FIELDS))
    _append_list_section(sections, "步骤", _first_value(record, STEP_FIELDS), ordered=True)
    _append_list_section(sections, "小贴士", _first_value(record, TIP_FIELDS))

    # 结构化记录常常有自定义字段；保留未归类文本可以提升长尾问题召回率。
    used_fields = set(TITLE_FIELDS + INGREDIENT_FIELDS + SEASONING_FIELDS + STEP_FIELDS + TIP_FIELDS)
    extra_lines = [
        f"- {key}: {_stringify_value(value)}"
        for key, value in record.items()
        if key not in used_fields and _stringify_value(value)
    ]
    if extra_lines:
        sections.append("## 其他信息\n" + "\n".join(extra_lines))

    return "\n\n".join(section for section in sections if section.strip())


def _render_overview_lines(record: dict[str, Any]) -> list[str]:
    overview_keys = (
        "category",
        "分类",
        "cuisine",
        "菜系",
        "servings",
        "份量",
        "time",
        "耗时",
        "difficulty",
        "难度",
    )
    return [
        f"- {key}: {_stringify_value(record[key])}"
        for key in overview_keys
        if key in record and _stringify_value(record[key])
    ]


def _append_list_section(
    sections: list[str],
    title: str,
    value: Any,
    *,
    ordered: bool = False,
) -> None:
    items = _coerce_list(value)
    if not items:
        return

    if ordered:
        lines = [f"{index}. {item}" for index, item in enumerate(items, start=1)]
    else:
        lines = [f"- {item}" for item in items]
    sections.append(f"## {title}\n" + "\n".join(lines))


def _build_base_metadata(path: Path, data_dir: Path, *, document_format: str) -> dict[str, Any]:
    relative_path = path.relative_to(data_dir)
    category_parts = relative_path.parts[:-1]

    return {
        "source_path": relative_path.as_posix(),
        "category": "/".join(category_parts),
        "file_name": path.name,
        "document_format": document_format,
    }


def _extract_title_from_text(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
        if stripped:
            return None
    return None


def _first_text(record: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    value = _first_value(record, fields)
    text = _stringify_value(value)
    return text or None


def _first_value(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = record.get(field)
        if _stringify_value(value):
            return value
    return None


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [text for item in value if (text := _stringify_value(item))]
    if isinstance(value, dict):
        return [
            f"{key}: {_stringify_value(item)}"
            for key, item in value.items()
            if _stringify_value(item)
        ]

    text = _stringify_value(value)
    if not text:
        return []

    separators = ("\n", "；", ";", "、")
    items = [text]
    for separator in separators:
        if separator in text:
            items = [part.strip() for part in text.split(separator)]
            break

    return [item for item in items if item]


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "；".join(item for item in (_stringify_value(item) for item in value) if item)
    if isinstance(value, dict):
        return "；".join(
            f"{key}: {text}"
            for key, item in value.items()
            if (text := _stringify_value(item))
        )
    return str(value).strip()
