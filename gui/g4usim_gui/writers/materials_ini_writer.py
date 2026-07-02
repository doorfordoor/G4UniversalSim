from __future__ import annotations

from pathlib import Path

from g4usim_gui.editors.material_editor_model import MaterialDocument, generate_materials_ini_text, validate_material_document


def write_materials_ini(path: str | Path, document: MaterialDocument) -> str:
    validate_material_document(document)
    if document.errors:
        raise ValueError("Materials Editor validation failed:\n" + "\n".join(document.errors))
    text = generate_materials_ini_text(document)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    document.generated_path = str(target)
    return text
