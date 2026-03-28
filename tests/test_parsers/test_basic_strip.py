"""Tests for app.parsers.basic_strip."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper, FakeFact
from app.parsers.basic_strip import Parser


class TestBasicStripParser:

    def _parser(self, mappers=None, used_facts=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = used_facts or []
        return p

    def test_single_line_single_mapper(self):
        mp = FakeMapper(source='src.trait', edge='edge1', target='tgt.trait')
        p = self._parser(mappers=[mp])
        result = p.parse('  hello  ')
        assert len(result) == 1
        assert result[0].source.trait == 'src.trait'
        assert result[0].source.value == 'hello'
        assert result[0].edge == 'edge1'
        assert result[0].target.trait == 'tgt.trait'
        assert result[0].target.value == 'hello'

    def test_multi_line(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('line1\nline2\nline3')
        assert len(result) == 3

    def test_strips_whitespace(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('   value   ')
        assert result[0].source.value == 'value'

    def test_multiple_mappers(self):
        mp1 = FakeMapper(source='s1', edge='e1', target='t1')
        mp2 = FakeMapper(source='s2', edge='e2', target='t2')
        p = self._parser(mappers=[mp1, mp2])
        result = p.parse('val')
        assert len(result) == 2
        assert result[0].source.trait == 's1'
        assert result[1].source.trait == 's2'

    def test_empty_blob(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('')
        assert result == []

    def test_no_mappers(self):
        p = self._parser(mappers=[])
        result = p.parse('something')
        assert result == []
