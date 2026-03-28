"""Tests for app.parsers.key_value."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper
from app.parsers.key_value import Parser


class TestKeyValueParser:

    def _parser(self, mappers=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = []
        return p

    def test_single_pair(self):
        mp = FakeMapper(source='file.path', edge='has_hash', target='file.hash')
        p = self._parser(mappers=[mp])
        result = p.parse('/tmp/a.txt > abc123')
        assert len(result) == 1
        assert result[0].source.value == '/tmp/a.txt'
        assert result[0].target.value == 'abc123'
        assert result[0].edge == 'has_hash'

    def test_multi_line(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        blob = 'key1 > val1\nkey2 > val2'
        result = p.parse(blob)
        assert len(result) == 2
        assert result[0].source.value == 'key1'
        assert result[1].target.value == 'val2'

    def test_strips_whitespace(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('  k  >  v  ')
        assert result[0].source.value == 'k'
        assert result[0].target.value == 'v'

    def test_empty_blob(self):
        mp = FakeMapper(source='s', edge='e', target='t')
        p = self._parser(mappers=[mp])
        result = p.parse('')
        assert result == []

    def test_multiple_mappers(self):
        mp1 = FakeMapper(source='s1', edge='e1', target='t1')
        mp2 = FakeMapper(source='s2', edge='e2', target='t2')
        p = self._parser(mappers=[mp1, mp2])
        result = p.parse('a > b')
        assert len(result) == 2
