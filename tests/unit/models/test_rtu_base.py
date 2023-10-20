from typing import Type

import pytest

from origami.models.rtu.base import BaseRTU, BaseRTURequest, BaseRTUResponse


@pytest.mark.parametrize("clazz", [BaseRTU, BaseRTURequest, BaseRTUResponse])
class TestRTUFamily:
    def test_set_channel_prefix(self, clazz: Type[BaseRTU]):
        """Channel prefix is derived from channel."""
        obj = clazz(
            channel="foo/12345",
            event="foo_event",
        )

        assert obj.channel_prefix == "foo"

    def test_channel_prefix_does_not_serialize(self, clazz):
        """channel_prefix should not be part of object serialization"""
        obj = clazz(
            channel="foo/12345",
            event="foo_event",
        )

        assert "channel_prefix" not in obj.model_dump_json()
