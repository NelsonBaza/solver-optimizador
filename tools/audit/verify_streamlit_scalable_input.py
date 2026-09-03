"""Recorridos interactivos reproducibles de entrada masiva con Streamlit AppTest."""

from __future__ import annotations

import io
import zipfile
from html import escape
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "streamlit_app.py"


def _wide_rows(count: int, delimiter: str = ",") -> str:
    rows = [delimiter.join(["name", "x1", "x2", "operator", "rhs"])]
    essentials = [
        ["R1", "1", "1", "<=", "4"],
        ["R2", "1", "0", "<=", "2"],
        ["R3", "0", "1", "<=", "3"],
    ]
    rows.extend(delimiter.join(row) for row in essentials)
    rows.extend(
        delimiter.join([f"R{index}", "1", "1", "<=", "1000"])
        for index in range(4, count + 1)
    )
    return "\n".join(rows)


def _sparse_rows(count: int) -> str:
    rows = ["constraint,variable,coefficient,operator,rhs"]
    rows.extend(
        [
            "R1,x1,1,<=,4",
            "R1,x2,1,<=,4",
            "R2,x1,1,<=,2",
            "R3,x2,1,<=,3",
        ]
    )
    for index in range(4, count + 1):
        rows.append(f"R{index},x1,1,<=,1000")
        rows.append(f"R{index},x2,1,<=,1000")
    return "\n".join(rows)


def _xlsx_bytes(csv_text: str) -> bytes:
    rows = [line.split(",") for line in csv_text.splitlines()]

    def cell(value: str, row: int, column: int) -> str:
        letters = ""
        cursor = column
        while cursor:
            cursor, remainder = divmod(cursor - 1, 26)
            letters = chr(65 + remainder) + letters
        reference = f"{letters}{row}"
        try:
            numeric = float(value)
        except ValueError:
            return f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
        return f'<c r="{reference}"><v>{numeric}</v></c>'

    xml_rows = []
    for row_index, values in enumerate(rows, start=1):
        cells = "".join(cell(value, row_index, column) for column, value in enumerate(values, 1))
        xml_rows.append(f'<row r="{row_index}">{cells}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Modelo" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


def _new_mono_app() -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    next(button for button in app.button if "Ejemplo 1 (Mono)" in button.label).click().run()
    assert not app.exception
    return app


def _set_mode(app: AppTest, mode: str) -> None:
    next(element for element in app.segmented_control if element.label == "Modo de entrada").set_value(mode).run()
    assert not app.exception


def _apply_and_solve(app: AppTest, expected_constraints: int) -> None:
    next(button for button in app.button if button.label == "Aplicar importacion").click().run()
    assert not app.exception
    assert len(app.session_state.constraints_data) == expected_constraints
    preview_tables = [
        table.value
        for table in app.dataframe
        if "Restriccion" in table.value.columns and "LHS disperso" in table.value.columns
    ]
    assert preview_tables and len(preview_tables[-1]) <= 20
    next(button for button in app.button if "Resolver Modelo" in button.label).click().run()
    assert not app.exception
    solution = app.session_state.last_solution
    assert solution is not None
    assert len(solution.constraint_results) == expected_constraints
    assert abs(solution.objective_value - 10.0) <= 1e-7


def verify_paste_50() -> None:
    app = _new_mono_app()
    _set_mode(app, "Pegar tabla")
    next(area for area in app.text_area if area.label.startswith("Pegue una tabla ancha")).set_value(
        _wide_rows(50, "\t")
    ).run()
    next(button for button in app.button if button.label == "Validar tabla pegada").click().run()
    assert app.session_state.constraint_import_preview.number_of_constraints == 50
    _apply_and_solve(app, 50)
    print("CASE 1 PASS: TSV paste, 50 constraints, preview<=20, solved all 50")


def verify_csv_100() -> None:
    app = _new_mono_app()
    _set_mode(app, "CSV / XLSX")
    uploader = next(item for item in app.file_uploader if item.label.startswith("Seleccione CSV"))
    uploader.upload("constraints_100.csv", _wide_rows(100).encode("utf-8-sig"), "text/csv").run()
    next(button for button in app.button if button.label == "Validar archivo").click().run()
    _apply_and_solve(app, 100)
    print("CASE 2 PASS: CSV UTF-8-SIG, 100 constraints, preview<=20, solved all 100")


def verify_xlsx_100() -> None:
    app = _new_mono_app()
    _set_mode(app, "CSV / XLSX")
    uploader = next(item for item in app.file_uploader if item.label.startswith("Seleccione CSV"))
    uploader.upload(
        "constraints_100.xlsx",
        _xlsx_bytes(_wide_rows(100)),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ).run()
    next(button for button in app.button if button.label == "Validar archivo").click().run()
    _apply_and_solve(app, 100)
    print("CASE 3 PASS: XLSX sheet Modelo, 100 constraints, preview<=20, solved all 100")


def verify_sparse_300() -> None:
    app = _new_mono_app()
    _set_mode(app, "Matriz dispersa")
    next(area for area in app.text_area if area.label.startswith("Tabla dispersa")).set_value(
        _sparse_rows(300)
    ).run()
    next(button for button in app.button if button.label == "Validar matriz dispersa").click().run()
    preview = app.session_state.constraint_import_preview
    assert preview.number_of_constraints == 300
    assert preview.nonzero_coefficients == 598
    _apply_and_solve(app, 300)
    print("CASE 4 PASS: sparse long, 300 constraints, 598 nonzeros, solved all 300")


def main() -> None:
    verify_paste_50()
    verify_csv_100()
    verify_xlsx_100()
    verify_sparse_300()
    print("RESULT: PASS (Streamlit scalable input interaction contract satisfied)")


if __name__ == "__main__":
    main()
