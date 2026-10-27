"""Generate the files that come from the configuration schema (roadmap E2).

Source: schema/config_schema.json. Outputs:

  include/Config/ConfigSchemaTable.hh        the backend's key table for migrated sections
                                             (ConfigManager uses it to recognise keys)
  gui/g4usim_gui/core/config_schema_data.py  the same data for the GUI's validator
                                             (a module, so the packaged GUI needs no data file)
  docs/功能支持矩阵.md                        the field tables between the GENERATED markers

    python scripts/generate_config_schema.py           write the files
    python scripts/generate_config_schema.py --check   exit 1 if any file is out of date
"""

from __future__ import annotations

import json
import pprint
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema/config_schema.json"
HEADER = ROOT / "include/Config/ConfigSchemaTable.hh"
PYTHON = ROOT / "gui/g4usim_gui/core/config_schema_data.py"
MATRIX = ROOT / "docs/功能支持矩阵.md"
COVERAGE = ROOT / "schema/config_schema_coverage.json"
BEGIN, END = "<!-- BEGIN GENERATED: config schema -->", "<!-- END GENERATED: config schema -->"

TYPES = {"int": "Int", "bool": "Bool", "string": "String", "enum": "Enum", "energy": "Energy",
         "existing_file": "ExistingFile", "length": "Length", "angle": "Angle", "time": "Time",
         "number": "Number", "structured": "Structured"}
SUPPORT_ZH = {"supported": "支持", "experimental": "实验性", "deprecated": "弃用（兼容）", "unsupported": "不支持"}
TYPE_ZH = {"int": "整数", "bool": "布尔", "string": "文本", "enum": "枚举", "energy": "能量",
           "existing_file": "现有文件", "length": "长度", "angle": "角度", "time": "时间",
           "number": "数值", "structured": "上下文相关结构"}
KEY_FIELDS = {"type", "aliases", "min", "max", "default", "allowed", "value_aliases", "support", "since",
              "description", "description_zh", "gui", "empty", "exclusive_min", "min_length",
              "syntax", "path_base", "validation", "parser", "tests", "recognition", "rules", "case_sensitive"}


def load_schema() -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    problems = []
    if schema.get("schema") != "g4usim_config_schema_v1":
        problems.append("schema must be g4usim_config_schema_v1")
    for file_name, file_spec in schema["files"].items():
        for section, spec in file_spec["sections"].items():
            if section != section.lower():
                problems.append(f"{file_name} [{section}]: section names are lower case")
            if not spec.get("independent"):
                for required in ("parser", "validation", "tests", "gui"):
                    if not spec.get(required):
                        problems.append(f"{file_name} [{section}]: {required} is required")
                for test in spec.get("tests", []):
                    if not (ROOT / test).is_file():
                        problems.append(f"{file_name} [{section}]: missing test {test}")
            names = set()
            for key, item in spec["keys"].items():
                where = f"{file_name} [{section}]/{key}"
                unknown = set(item) - KEY_FIELDS
                if unknown:
                    problems.append(f"{where}: unknown fields {sorted(unknown)}")
                if item.get("type") not in TYPES:
                    problems.append(f"{where}: type must be one of {sorted(TYPES)}")
                if item.get("support") not in SUPPORT_ZH:
                    problems.append(f"{where}: support must be one of {sorted(SUPPORT_ZH)}")
                for field in ("since", "description", "description_zh"):
                    if not item.get(field):
                        problems.append(f"{where}: {field} is required")
                if "default" not in item:
                    problems.append(f"{where}: default is required (null when there is none)")
                if item.get("empty", "default") != "default":
                    problems.append(f"{where}: empty can only be \"default\"")
                if item.get("type") == "enum" and not item.get("allowed"):
                    problems.append(f"{where}: an enum needs allowed values")
                for name in [key, *item.get("aliases", [])]:
                    if name.lower() in names:
                        problems.append(f"{where}: duplicate key/alias {name}")
                    names.add(name.lower())
    if problems:
        raise SystemExit("schema/config_schema.json:\n  " + "\n  ".join(problems))
    return schema


def migrated(schema: dict, file_name: str = "main_ini"):
    for section, spec in schema["files"][file_name]["sections"].items():
        if spec.get("migrated"):
            yield section, spec


def header_text(schema: dict) -> str:
    rows, sections = [], []
    for section, spec in migrated(schema):
        if "<" in section or spec.get("dynamic"):
            continue
        sections.append(f'"{section}"')
        for key, item in spec["keys"].items():
            aliases = ",".join(alias.lower() for alias in item.get("aliases", []))
            default = "nullptr" if item["default"] is None else json.dumps(item["default"])
            rows.append(f'    {{"{section}", "{key.lower()}", "{aliases}", ValueType::{TYPES[item["type"]]}, '
                        f'{default}, "{item["support"]}"}},')
    return "\n".join([
        "// Generated by scripts/generate_config_schema.py from schema/config_schema.json; do not edit.",
        "// The backend's key table for the sections migrated to the schema (roadmap E2).",
        "#pragma once",
        "",
        "namespace ConfigSchema {",
        "",
        "enum class ValueType { " + ", ".join(TYPES.values()) + " };",
        "",
        "struct KeySpec {",
        "    const char* section;       // lower case",
        "    const char* key;           // canonical name, lower case",
        "    const char* aliases;       // comma-separated, lower case",
        "    ValueType type;",
        "    const char* defaultValue;  // nullptr: no default (the engine or another field decides)",
        "    const char* support;       // supported, experimental or deprecated",
        "};",
        "",
        "// main INI sections whose keys come from the schema",
        f"inline constexpr const char* kMainIniSections[] = {{{', '.join(sections)}}};",
        "",
        "inline constexpr KeySpec kMainIniKeys[] = {",
        *rows,
        "};",
        "",
        "}  // namespace ConfigSchema",
        "",
    ]) + all_keys_header(schema)


def all_keys_header(schema: dict) -> str:
    """Exact schema identifiers; parsers retain their existing section-name grammar."""
    rows = []
    for file, _ in schema["files"].items():
        for section, spec in migrated(schema, file):
            for key, item in spec["keys"].items():
                for name in [key, *item.get("aliases", [])]:
                    rows.append("    {" + ", ".join(json.dumps(s) for s in (file, section, name.lower())) + ", " + ("false" if item.get("recognition") == "parser_only" else "true") + "},")
    return "\n".join([
        "#include <string>", "#include <vector>", "namespace ConfigSchema {",
        "struct FieldKey { const char* file; const char* section; const char* key; bool diagnostic; };",
        "inline constexpr FieldKey kFieldKeys[] = {", *rows, "};",
        "inline std::vector<std::string> Keys(const std::string& file, const std::string& section, bool diagnostic = false) {",
        "    std::vector<std::string> result;",
        "    for (const auto& field : kFieldKeys)",
        "        if (file == field.file && section == field.section && (!diagnostic || field.diagnostic)) result.emplace_back(field.key);",
        "    return result;", "}",
        "inline bool HasKey(const std::string& file, const std::string& section, const std::string& key, bool diagnostic = false) {",
        "    for (const auto& field : kFieldKeys)",
        "        if (file == field.file && section == field.section && key == field.key && (!diagnostic || field.diagnostic)) return true;",
        "    return false;", "}", "}  // namespace ConfigSchema", "",
    ])


def python_text(schema: dict) -> str:
    data = {file_name: {section: spec for section, spec in file_spec["sections"].items() if spec.get("migrated")}
            for file_name, file_spec in schema["files"].items()}
    return "\n".join([
        '"""Generated by scripts/generate_config_schema.py from schema/config_schema.json; do not edit.',
        "",
        "The migrated sections of the configuration schema (roadmap E2); read it through",
        'g4usim_gui.core.config_schema."""',
        "",
        f"SCHEMA = {pprint.pformat(data, width=110, sort_dicts=False)}",
        "",
    ])


def matrix_text(schema: dict) -> str:
    lines = [BEGIN, "",
             "以下字段表由 `scripts/generate_config_schema.py` 从 `schema/config_schema.json` 生成，请勿手工修改；"
             "`scripts/test_config_schema.py` 核对独立标量；上下文字段的规则、解析入口、校验阶段和专项测试列在 schema 中。"
             "尚未迁移的 section 仍以第 2 节的说明为准。", ""]
    for file_name, file_spec in schema["files"].items():
        for section, spec in migrated(schema, file_name):
            lines += [f"### `[{section}]`（{file_spec['title']}）", "", spec["description_zh"], "",
                      "| 键 | 别名 | 类型 | 取值 | 默认值 | 支持等级 | 起始 | 说明 |",
                      "|---|---|---|---|---|---|---|---|"]
            for key, item in spec["keys"].items():
                lines.append("| " + " | ".join([
                    f"`{key}`", ", ".join(f"`{a}`" for a in item.get("aliases", [])) or "-",
                    TYPE_ZH[item["type"]], value_range(item) + ("；空值取默认" if item.get("empty") else ""),
                    "-" if item["default"] is None else (f"`{item['default']}`" if item["default"] else "（空）"),
                    SUPPORT_ZH[item["support"]], item["since"], item["description_zh"]]) + " |")
            lines.append("")
            if spec.get("rules"):
                lines += ["约束：" + "；".join(spec["rules"]), ""]
            if spec.get("parser"):
                lines += [f"解析入口：`{spec['parser']}`；校验阶段：{spec.get('validation', 'configure')}。",
                          "回归：" + "、".join(f"`{t}`" for t in spec.get("tests", [])) + "。", ""]
    lines.append(END)
    return "\n".join(lines)


def value_range(item: dict) -> str:
    if item.get("syntax"):
        return item["syntax"].replace("|", " / ")
    kind = item["type"]
    if kind == "enum":
        text = " / ".join(f"`{v}`" for v in item["allowed"])
        text += "（区分大小写）" if item.get("case_sensitive") else ""
        aliases = item.get("value_aliases", {})
        return text + ("（" + "，".join(f"`{a}` = `{b}`" for a, b in aliases.items()) + "）" if aliases else "")
    if kind == "structured":
        return "依上下文；见本节约束与解析入口"
    if kind in {"int", "energy", "length", "time", "angle", "number"}:
        low, high = item.get("min"), item.get("max")
        unit = {"energy": " MeV", "length": " mm", "time": " ns", "angle": " rad"}.get(kind, "")
        if item.get("exclusive_min") is not None:
            return f"> {item['exclusive_min']}{unit}"
        if low is not None and high is not None and abs(high) == 2147483647 and low in (-2147483648,):
            return "32 位整数"
        if low is not None and high is not None and high != 2147483647:
            return f"{low}–{high}{unit}"
        if low is not None:
            return f"≥ {low}{unit}" + ("，可带 eV/keV/MeV/GeV" if kind == "energy" else "")
        return "有限数值" + unit
    if kind == "bool":
        return "true/false（yes/no、on/off、1/0）"
    if kind == "existing_file":
        return "存在的文件或空"
    return "单行文本"


def outputs(schema: dict) -> dict[Path, str]:
    matrix = MATRIX.read_text(encoding="utf-8").replace("\r\n", "\n")
    if matrix.count(BEGIN) != 1 or matrix.count(END) != 1:
        raise SystemExit(f"{MATRIX.name} needs exactly one {BEGIN} ... {END} block")
    start, end = matrix.index(BEGIN), matrix.index(END) + len(END)
    coverage = []
    for file_name in schema["files"]:
        for section, definition in migrated(schema, file_name):
            for key, item in definition["keys"].items():
                coverage.append(dict(file=file_name, section=section, key=key,
                                     scalar_check=item["type"] != "structured",
                                     parser=item.get("parser", definition.get("parser", "src/Core/SimulationManager.cc:Configure")),
                                     validation=item.get("validation", definition.get("validation", "configure")),
                                     gui=item.get("gui", definition.get("gui", {"editable": "existing_subset_only"})),
                                     tests=item.get("tests", definition.get("tests", ["scripts/test_config_schema.py"]))))
    return {HEADER: header_text(schema), PYTHON: python_text(schema),
            COVERAGE: json.dumps({"generated_by": "scripts/generate_config_schema.py", "fields": coverage,
                                 "excluded": schema.get("excluded", {})}, ensure_ascii=False, indent=2) + "\n",
            MATRIX: matrix[:start] + matrix_text(schema) + matrix[end:]}


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, text in outputs(load_schema()).items():
        current = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.is_file() else None
        if current == text:
            continue
        if check:
            stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT).as_posix()}")
    if stale:
        print("out of date (run scripts/generate_config_schema.py): " + ", ".join(stale))
        return 1
    if check:
        print("generated files are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
