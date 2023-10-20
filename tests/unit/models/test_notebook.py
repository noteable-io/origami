from uuid import uuid4

import pytest

from origami.models.notebook import CellBase, StreamOutput


class TestStreamOutput:
    @pytest.mark.parametrize("text_value", [["this", "is", "multiline"], "this\nis\nmultiline"])
    def test_multiline_text(self, text_value):
        output = StreamOutput(name="output", text=text_value)

        assert output.text == "this\nis\nmultiline"


class TestCellBase:
    @pytest.mark.parametrize("source_value", [["this", "is", "multiline"], "this\nis\nmultiline"])
    def test_multiline_source(self, source_value):
        cell = CellBase(id=str(uuid4()), source=source_value)

        assert cell.source == "this\nis\nmultiline"
