"""Tests for app.parsers.childprocess."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper, FakeFact
from app.parsers.childprocess import Parser


class TestChildProcessParser:

    def _parser(self, mappers=None, used_facts=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = used_facts or []
        return p

    def test_parse_childid_regex(self):
        blob = 'ProcessId: 1234\nSomething else\nProcessId: 5678'
        result = Parser.parse_childid(blob)
        assert result == ['1234', '5678']

    def test_parse_childid_case_insensitive(self):
        blob = 'processid: 42'
        result = Parser.parse_childid(blob)
        assert result == ['42']

    def test_parse_childid_no_match(self):
        result = Parser.parse_childid('nothing here')
        assert result == []

    def test_parse_single_match(self):
        mp = FakeMapper(source='host.process.guid', edge='has_childprocess_id', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='guid-abc')
        p = self._parser(mappers=[mp], used_facts=[fact])
        blob = 'ProcessId: 999'
        result = p.parse(blob)
        assert len(result) == 1
        assert result[0].source.value == 'guid-abc'
        assert result[0].target.value == '999'

    def test_parse_multiple_matches(self):
        mp = FakeMapper(source='host.process.guid', edge='has_childprocess_id', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='guid-abc')
        p = self._parser(mappers=[mp], used_facts=[fact])
        blob = 'ProcessId: 100\nProcessId: 200'
        result = p.parse(blob)
        assert len(result) == 2
        assert result[0].target.value == '100'
        assert result[1].target.value == '200'

    def test_parse_no_match_returns_empty(self):
        mp = FakeMapper(source='host.process.guid', edge='e', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='g')
        p = self._parser(mappers=[mp], used_facts=[fact])
        result = p.parse('no match')
        assert result == []

    def test_parse_appends_to_used_facts(self):
        mp = FakeMapper(source='host.process.guid', edge='e', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='g')
        facts_list = [fact]
        p = self._parser(mappers=[mp], used_facts=facts_list)
        p.parse('ProcessId: 10')
        # The parser appends r.target to all_facts (which is self.used_facts)
        assert len(facts_list) == 2
