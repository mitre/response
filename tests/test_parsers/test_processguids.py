"""Tests for app.parsers.processguids."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper, FakeFact
from app.parsers.processguids import Parser


class TestProcessGuidsParser:

    def _parser(self, mappers=None, used_facts=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = used_facts or []
        return p

    # ── Static regex methods ─────────────────────────────────────────────

    def test_parse_id(self):
        blob = 'ProcessId: 1234'
        assert Parser.parse_id(blob) == ['1234']

    def test_parse_id_case_insensitive(self):
        assert Parser.parse_id('processid: 99') == ['99']

    def test_parse_id_multiple(self):
        blob = 'ProcessId: 1\nProcessId: 2'
        assert Parser.parse_id(blob) == ['1', '2']

    def test_parse_id_no_match(self):
        assert Parser.parse_id('nothing') == []

    def test_parse_guid(self):
        blob = 'ProcessGuid: {abc-def-123}'
        assert Parser.parse_guid(blob) == ['abc-def-123']

    def test_parse_guid_case_insensitive(self):
        assert Parser.parse_guid('processguid: {XYZ}') == ['XYZ']

    def test_parse_guid_no_match(self):
        assert Parser.parse_guid('no guid') == []

    def test_parse_parentid(self):
        blob = 'ParentProcessId: 5678'
        assert Parser.parse_parentid(blob) == ['5678']

    def test_parse_parentid_case_insensitive(self):
        assert Parser.parse_parentid('parentprocessid: 77') == ['77']

    def test_parse_parentguid(self):
        blob = 'ParentProcessGuid: {parent-guid}'
        assert Parser.parse_parentguid(blob) == ['parent-guid']

    def test_parse_parentguid_case_insensitive(self):
        assert Parser.parse_parentguid('parentprocessguid: {PG}') == ['PG']

    # ── parse_options ────────────────────────────────────────────────────

    def test_parse_options_keys(self):
        p = self._parser()
        assert set(p.parse_options.keys()) == {'id', 'guid', 'parentid', 'parentguid'}

    # ── parse ────────────────────────────────────────────────────────────

    def test_parse_with_id_mapper(self):
        mp = FakeMapper(source='host.process.guid', edge='has_childprocess_id', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='my-guid')
        p = self._parser(mappers=[mp], used_facts=[fact])
        blob = 'ProcessId: 42'
        result = p.parse(blob)
        assert len(result) == 1
        assert result[0].source.value == 'my-guid'
        assert result[0].target.value == '42'

    def test_parse_with_guid_mapper(self):
        mp = FakeMapper(source='host.process.id', edge='has_guid', target='host.process.guid')
        fact = FakeFact(trait='host.process.id', value='100')
        p = self._parser(mappers=[mp], used_facts=[fact])
        blob = 'ProcessGuid: {guid-abc}'
        result = p.parse(blob)
        assert len(result) == 1
        assert result[0].target.value == 'guid-abc'

    def test_parse_no_match(self):
        mp = FakeMapper(source='s', edge='e', target='host.process.id')
        fact = FakeFact(trait='s', value='v')
        p = self._parser(mappers=[mp], used_facts=[fact])
        result = p.parse('nothing')
        assert result == []

    def test_parse_appends_target_to_facts(self):
        mp = FakeMapper(source='host.process.guid', edge='e', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='g')
        facts_list = [fact]
        p = self._parser(mappers=[mp], used_facts=facts_list)
        p.parse('ProcessId: 10')
        assert len(facts_list) == 2

    def test_parse_multiple_matches(self):
        mp = FakeMapper(source='host.process.guid', edge='e', target='host.process.id')
        fact = FakeFact(trait='host.process.guid', value='g')
        p = self._parser(mappers=[mp], used_facts=[fact])
        blob = 'ProcessId: 10\nProcessId: 20'
        result = p.parse(blob)
        assert len(result) == 2
