"""Contratos de importacion escalable y aplicacion atomica al estado."""

from __future__ import annotations

import io
import zipfile
from html import escape

import pytest

from solver_optimizador.constraint_import import (
    constraints_to_sparse_csv,
    list_xlsx_sheets,
    parse_constraint_text,
    parse_objective_text,
    parse_variable_names,
    parse_xlsx_constraints,
)
from solver_optimizador.input_application import (
    apply_constraint_import,
    apply_objective_import,
    apply_variable_import,
)
from solver_optimizador.lp_models import SolverStatus
from solver_optimizador.lp_solver import solve_lp
from solver_optimizador.model_io import deserialize_model, serialize_model
from solver_optimizador.multiobjective import solve_biobjective_weighted
from solver_optimizador.problem_builder import (
    build_biobjective_problem_from_state,
    build_lp_problem_from_state,
)


WIDE_TEXT = """name,x1,x2,x3,operator,rhs
R1,2,3,0,<=,20
R2,0,1,4,>=,15
R3,1,0,-2,=,7
"""


def _make_xlsx(rows: list[list[object]]) -> bytes:
    def cell_xml(value: object, row: int, column: int) -> str:
        letters = ""
        index = column
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        reference = f"{letters}{row}"
        if isinstance(value, (int, float)):
            return f'<c r="{reference}"><v>{value}</v></c>'
        return (
            f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
        )

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            cell_xml(value, row_index, column_index)
            for column_index, value in enumerate(row, start=1)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Modelo" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def _initial_state() -> dict[str, object]:
    return {
        "editor_version": 4,
        "problem_type": "Monoobjetivo",
        "num_vars": 2,
        "var_names": ["x1", "x2"],
        "obj_coeffs": {"x1": 7.0, "x2": 8.0},
        "obj1_coeffs": {"x1": 1.0, "x2": 2.0},
        "obj2_coeffs": {"x1": 3.0, "x2": 4.0},
        "constraints_data": [
            {"name": "old", "coefficients": {"x1": 1.0}, "operator": "<=", "rhs": 1.0}
        ],
        "last_solution": object(),
        "last_solution_type": "Monoobjetivo",
        "last_solution_problem": object(),
        "last_solution_signature": "old",
    }


def test_wide_csv_basic_is_sparse():
    result = parse_constraint_text(WIDE_TEXT)
    assert result.is_valid
    assert result.number_of_constraints == 3
    assert result.detected_variables == ["x1", "x2", "x3"]
    assert result.nonzero_coefficients == 6
    assert result.constraints[0]["coefficients"] == {"x1": 2.0, "x2": 3.0}


def test_excel_tsv_paste():
    text = "name\tx1\tx2\toperator\trhs\nR1\t2\t3\t<=\t20\n"
    result = parse_constraint_text(text)
    assert result.is_valid
    assert result.source_format == "tsv_wide"
    assert result.constraints[0]["coefficients"] == {"x1": 2.0, "x2": 3.0}


def test_semicolon_csv():
    result = parse_constraint_text("name;x1;x2;operator;rhs\nR1;2;3;<=;20\n")
    assert result.is_valid
    assert result.source_format == "semicolon_wide"


def test_xlsx_generated_temporarily(tmp_path):
    data = _make_xlsx(
        [
            ["name", "x1", "x2", "operator", "rhs"],
            ["R1", 2, 3, "<=", 20],
            ["R2", 0, 1, ">=", 15],
        ]
    )
    path = tmp_path / "constraints.xlsx"
    path.write_bytes(data)
    assert list_xlsx_sheets(path.read_bytes()) == ["Modelo"]
    result = parse_xlsx_constraints(path.read_bytes(), sheet_name="Modelo")
    assert result.is_valid
    assert result.number_of_constraints == 2
    assert result.constraints[1]["coefficients"] == {"x2": 1.0}


def test_xlsx_with_vba_payload_is_rejected(tmp_path):
    path = tmp_path / "renamed_macro.xlsx"
    path.write_bytes(
        _make_xlsx(
            [["name", "x1", "operator", "rhs"], ["R1", 1, "<=", 10]]
        )
    )
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/vbaProject.bin", b"not-executed")
    result = parse_xlsx_constraints(path.read_bytes(), sheet_name="Modelo")
    assert not result.is_valid
    assert any("macros VBA" in error for error in result.errors)


def test_sparse_long_valid():
    text = """constraint,variable,coefficient,operator,rhs
R1,x1,2,<=,20
R1,x7,5,<=,20
R1,x18,-1,<=,20
R2,x4,3,>=,15
R2,x21,7,>=,15
"""
    result = parse_constraint_text(text, input_format="sparse")
    assert result.is_valid
    assert result.number_of_constraints == 2
    assert result.nonzero_coefficients == 5
    assert result.constraints[0]["coefficients"] == {"x1": 2.0, "x7": 5.0, "x18": -1.0}


def test_sparse_inconsistent_operator_fails():
    text = "constraint,variable,coefficient,operator,rhs\nR1,x1,2,<=,20\nR1,x2,5,>=,20\n"
    result = parse_constraint_text(text, input_format="sparse")
    assert not result.is_valid
    assert any("operador inconsistente" in error for error in result.errors)


def test_sparse_inconsistent_rhs_fails():
    text = "constraint,variable,coefficient,operator,rhs\nR1,x1,2,<=,20\nR1,x2,5,<=,30\n"
    result = parse_constraint_text(text, input_format="sparse")
    assert not result.is_valid
    assert any("RHS inconsistente" in error for error in result.errors)


def test_sparse_duplicate_pair_fails_without_summing():
    text = "constraint,variable,coefficient,operator,rhs\nR1,x1,2,<=,20\nR1,x1,5,<=,20\n"
    result = parse_constraint_text(text, input_format="sparse")
    assert not result.is_valid
    assert result.constraints[0]["coefficients"] == {"x1": 2.0}
    assert any("par duplicado" in error for error in result.errors)


@pytest.mark.parametrize("invalid", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_coefficients_and_rhs_fail(invalid):
    coefficient = parse_constraint_text(
        f"name,x1,operator,rhs\nR1,{invalid},<=,20\n"
    )
    rhs = parse_constraint_text(f"name,x1,operator,rhs\nR1,1,<=,{invalid}\n")
    assert not coefficient.is_valid
    assert not rhs.is_valid
    assert any("NaN e Infinity" in error for error in coefficient.errors + rhs.errors)


def test_wide_variable_inference():
    assert parse_constraint_text(WIDE_TEXT).detected_variables == ["x1", "x2", "x3"]


def test_sparse_variable_inference_preserves_first_seen_order():
    text = "constraint,variable,coefficient,operator,rhs\nR1,x7,2,<=,20\nR1,x1,5,<=,20\n"
    assert parse_constraint_text(text, input_format="sparse").detected_variables == ["x7", "x1"]


@pytest.mark.parametrize("count", [50, 500])
def test_bulk_wide_constraint_counts(count):
    rows = ["name,x1,x2,operator,rhs"]
    rows.extend(f"R{index},1,0,<=,{index + 10}" for index in range(1, count + 1))
    result = parse_constraint_text("\n".join(rows))
    assert result.is_valid
    assert result.number_of_constraints == count
    assert result.nonzero_coefficients == count


def test_sparse_1000_by_100_is_not_densified():
    rows = ["constraint,variable,coefficient,operator,rhs"]
    for index in range(1000):
        first = f"x{index % 100 + 1}"
        second = f"x{(index + 1) % 100 + 1}"
        rows.append(f"R{index + 1},{first},1,<=,20")
        rows.append(f"R{index + 1},{second},1,<=,20")
    result = parse_constraint_text("\n".join(rows), input_format="sparse")
    assert result.is_valid
    assert result.number_of_constraints == 1000
    assert result.number_of_variables == 100
    assert result.nonzero_coefficients == 2000
    assert all(len(row["coefficients"]) == 2 for row in result.constraints)
    variables = [f"x{index}" for index in range(1, 101)]
    problem = build_lp_problem_from_state(
        variables,
        "Maximizar",
        {},
        result.constraints,
    )
    assert sum(len(row.coefficients) for row in problem.constraints) == 2000


def test_manual_and_imported_lp_are_algebraically_equivalent():
    imported = parse_constraint_text(
        "name,x1,x2,operator,rhs\nCap,1,1,<=,4\nX1,1,0,<=,2\nX2,0,1,<=,3\n"
    )
    manual_rows = [
        {"name": "Cap", "coefficients": {"x1": 1.0, "x2": 1.0}, "operator": "<=", "rhs": 4.0},
        {"name": "X1", "coefficients": {"x1": 1.0}, "operator": "<=", "rhs": 2.0},
        {"name": "X2", "coefficients": {"x2": 1.0}, "operator": "<=", "rhs": 3.0},
    ]
    kwargs = dict(var_names=["x1", "x2"], obj_sense="Maximizar", obj_coeffs={"x1": 3.0, "x2": 2.0})
    manual = solve_lp(build_lp_problem_from_state(**kwargs, canonical_constraints=manual_rows))
    batch = solve_lp(build_lp_problem_from_state(**kwargs, canonical_constraints=imported.constraints))
    assert manual.status == batch.status == SolverStatus.OPTIMAL
    assert batch.objective_value == pytest.approx(manual.objective_value)
    assert batch.variable_values == pytest.approx(manual.variable_values)


def test_benchmark_a_biobjective_from_import():
    imported = parse_constraint_text(
        "name,x1,x2,operator,rhs\nR1,1,1,<=,130\nR2,2.5,1,<=,250\n"
    )
    problem = build_biobjective_problem_from_state(
        ["x1", "x2"],
        "Maximizar",
        {"x1": 10.0, "x2": 3.0},
        "Maximizar",
        {"x1": 0.8, "x2": 1.3},
        imported.constraints,
    )
    weights = [(0.0, 1.0), (0.2, 0.8), (0.4, 0.6), (0.5, 0.5), (0.6, 0.4), (0.8, 0.2), (1.0, 0.0)]
    expected = [(0, 130), (0, 130), (80, 50), (80, 50), (80, 50), (80, 50), (100, 0)]
    solution = solve_biobjective_weighted(problem, weights=weights)
    for run, point in zip(solution.weighted_runs, expected):
        assert run["x"] == pytest.approx({"x1": point[0], "x2": point[1]})


def test_constraint_batch_application_persists_and_invalidates_solution():
    state = _initial_state()
    result = parse_constraint_text(WIDE_TEXT)
    apply_constraint_import(state, result, use_detected_variables=True, source_metadata={"filename": "batch.csv"})
    assert state["var_names"] == ["x1", "x2", "x3"]
    assert len(state["constraints_data"]) == 3
    assert state["obj_coeffs"] == {"x1": 7.0, "x2": 8.0, "x3": 0.0}
    assert state["last_solution"] is None
    assert state["editor_version"] == 5
    assert state["constraint_import_metadata"]["filename"] == "batch.csv"


def test_mono_objective_import_and_omitted_variables_become_zero():
    state = _initial_state()
    result = parse_objective_text(
        "variable,coefficient\nx1,10\n", problem_type="Monoobjetivo", declared_variables=["x1", "x2"]
    )
    assert result.is_valid
    apply_objective_import(state, result)
    assert state["obj_coeffs"] == {"x1": 10.0, "x2": 0.0}


def test_biobjective_import():
    state = _initial_state()
    state["problem_type"] = "Biobjetivo"
    result = parse_objective_text(
        "variable,Z1,Z2\nx1,10,0.8\nx2,3,1.3\n",
        problem_type="Biobjetivo",
        declared_variables=["x1", "x2"],
    )
    assert result.is_valid
    apply_objective_import(state, result)
    assert state["obj1_coeffs"] == {"x1": 10.0, "x2": 3.0}
    assert state["obj2_coeffs"] == {"x1": 0.8, "x2": 1.3}


def test_unknown_variable_fails_in_strict_constraint_and_objective_modes():
    constraints = parse_constraint_text(
        "name,x1,x99,operator,rhs\nR1,1,2,<=,10\n",
        declared_variables=["x1"],
        strict_variables=True,
    )
    objective = parse_objective_text(
        "variable,coefficient\nx99,2\n",
        problem_type="Monoobjetivo",
        declared_variables=["x1"],
    )
    assert not constraints.is_valid
    assert not objective.is_valid
    assert any("x99" in error for error in constraints.errors + objective.errors)


def test_variable_block_import_preserves_known_coefficients_and_projects_constraints():
    state = _initial_state()
    result = parse_variable_names("x2\nx3\tx4")
    assert result.is_valid
    apply_variable_import(state, result)
    assert state["var_names"] == ["x2", "x3", "x4"]
    assert state["obj_coeffs"] == {"x2": 8.0, "x3": 0.0, "x4": 0.0}
    assert state["constraints_data"][0]["coefficients"] == {}


def test_invalid_batch_is_atomic():
    state = _initial_state()
    before = state.copy()
    invalid = parse_constraint_text(
        "constraint,variable,coefficient,operator,rhs\nR1,x1,1,<=,10\nR1,x1,2,<=,10\n",
        input_format="sparse",
    )
    with pytest.raises(ValueError, match="No se puede aplicar"):
        apply_constraint_import(state, invalid, use_detected_variables=False)
    assert state == before


def test_sparse_export_roundtrip():
    original = parse_constraint_text(WIDE_TEXT)
    exported = constraints_to_sparse_csv(original.constraints)
    restored = parse_constraint_text(exported, input_format="sparse")
    assert restored.is_valid
    assert restored.constraints == original.constraints


def test_json_roundtrip_preserves_sparse_canonical_constraints():
    variables = [f"x{index}" for index in range(1, 101)]
    constraints = [
        {
            "name": "Sparse",
            "coefficients": {"x1": 2.0, "x100": -3.0},
            "operator": "<=",
            "rhs": 10.0,
        }
    ]
    encoded = serialize_model(
        {
            "type": "Monoobjetivo",
            "variables": variables,
            "mono_objective": {"sense": "Maximizar", "coefficients": {}},
            "constraints": constraints,
        }
    )
    loaded = deserialize_model(encoded)
    assert loaded["constraints_data"][0]["coefficients"] == {
        "x1": 2.0,
        "x100": -3.0,
    }
    assert len(loaded["constraints_data"][0]["coefficients"]) == 2
