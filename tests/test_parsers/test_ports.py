"""Tests for app.parsers.ports."""
import sys
import json
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper
from app.parsers.ports import Parser


class TestPortsParser:

    def _parser(self, mappers=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = []
        return p

    def test_single_entry(self):
        mp = FakeMapper(source='host.process.id', edge='has_port', target='host.port')
        p = self._parser(mappers=[mp])
        blob = json.dumps([{'pid': '1234', 'port': '8080'}])
        result = p.parse(blob)
        assert len(result) == 1
        assert result[0].source.value == '1234'
        assert result[0].target.value == '8080'

    def test_multiple_entries(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        blob = json.dumps([
            {'pid': '1', 'port': '80'},
            {'pid': '2', 'port': '443'},
        ])
        result = p.parse(blob)
        assert len(result) == 2

    def test_empty_array(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('[]')
        assert result == []

    def test_multiple_mappers(self):
        mp1 = FakeMapper(source='s1', edge='e1', target='t1')
        mp2 = FakeMapper(source='s2', edge='e2', target='t2')
        p = self._parser(mappers=[mp1, mp2])
        blob = json.dumps([{'pid': '1', 'port': '80'}])
        result = p.parse(blob)
        assert len(result) == 2
