from origami.models.notebook import make_sql_cell


def test_sql_cell():
    cell = make_sql_cell(source="SELECT * FROM table")
    assert cell.is_sql_cell
    assert cell.source == "SELECT * FROM table"
    assert cell.metadata["noteable"]["db_connection"] == "@noteable"


def test_strip_sql_magic_prefix():
    cell = make_sql_cell(source="%%sql @noteable\nSELECT * FROM table")
    assert cell.is_sql_cell
    assert cell.source == "SELECT * FROM table"
    assert cell.metadata["noteable"]["db_connection"] == "@noteable"
