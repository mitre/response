"""Tests for app.parsers.process."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper
from app.parsers.process import Parser


class TestProcessParser:

    def _parser(self, mappers=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = []
        return p

    def test_single_line(self):
        mp = FakeMapper(source='host.process.id', edge='has', target='host.process.name')
        p = self._parser(mappers=[mp])
        result = p.parse('1234  cmd.exe')
        assert len(result) == 1
        assert result[0].source.value == '1234  cmd.exe'

    def test_multi_line(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('line1\nline2\nline3')
        assert len(result) == 3

    def test_empty_blob(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        # Empty string -> line() returns [''] but the parser processes it
        result = p.parse('')
        # splitlines on '' returns [] so no matches
        assert len(result) == 0

    def test_no_mappers(self):
        p = self._parser(mappers=[])
        result = p.parse('something')
        assert result == []

    def test_multiple_mappers(self):
        mp1 = FakeMapper(source='s1', edge='e1', target='t1')
        mp2 = FakeMapper(source='s2', edge='e2', target='t2')
        p = self._parser(mappers=[mp1, mp2])
        result = p.parse('val')
        assert len(result) == 2
