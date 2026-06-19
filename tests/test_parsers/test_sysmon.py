"""Tests for app.parsers.sysmon."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper, FakeFact
from app.parsers.sysmon import Parser


class TestSysmonParser:

    def _parser(self, mappers=None, used_facts=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = used_facts or []
        return p

    # ── Static regex methods ─────────────────────────────────────────────

    def test_parse_eventid(self):
        event = 'Id : 1\nOther: stuff'
        m = Parser.parse_eventid(event)
        assert m is not None
        assert m.group(1) == '1'

    def test_parse_eventid_no_match(self):
        assert Parser.parse_eventid('nothing') is None

    def test_parse_recordid(self):
        event = 'RecordId : 42'
        m = Parser.parse_recordid(event)
        assert m is not None
        assert m.group(1) == '42'

    def test_parse_recordid_no_match(self):
        assert Parser.parse_recordid('nothing') is None

    def test_parse_user(self):
        event = 'User: CORP\\admin'
        m = Parser.parse_user(event)
        assert m is not None
        assert m.group(1) == 'CORP\\admin'

    def test_parse_user_no_match(self):
        assert Parser.parse_user('nothing') is None

    # ── parse_options ────────────────────────────────────────────────────

    def test_parse_options_keys(self):
        p = self._parser()
        assert set(p.parse_options.keys()) == {'eventid', 'recordid', 'user'}

    # ── parse ────────────────────────────────────────────────────────────

    def test_parse_single_event(self):
        mp = FakeMapper(source='host.process.guid', edge='has_eventid', target='sysmon.eventid')
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        p = self._parser(mappers=[mp], used_facts=[fact])
        # The sysmon parser splits on \r\n\r\n; within an event the regex
        # captures everything after "Id : " including a trailing \r
        event = 'Id : 5\r\nRecordId : 100'
        result = p.parse(event)
        assert len(result) == 1
        assert result[0].source.value == 'guid-1'
        assert result[0].target.value.strip() == '5'

    def test_parse_multiple_events(self):
        mp = FakeMapper(source='host.process.guid', edge='has_eventid', target='sysmon.eventid')
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        p = self._parser(mappers=[mp], used_facts=[fact])
        events = 'Id : 1\r\n\r\nId : 2'
        result = p.parse(events)
        assert len(result) == 2

    def test_parse_no_match_returns_empty(self):
        mp = FakeMapper(source='s', edge='e', target='sysmon.eventid')
        fact = FakeFact(trait='s', value='v')
        p = self._parser(mappers=[mp], used_facts=[fact])
        result = p.parse('nothing here')
        assert result == []

    def test_parse_recordid_mapper(self):
        mp = FakeMapper(source='host.process.guid', edge='has_recordid', target='sysmon.recordid')
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        p = self._parser(mappers=[mp], used_facts=[fact])
        event = 'RecordId : 777'
        result = p.parse(event)
        assert len(result) == 1
        assert result[0].target.value == '777'

    def test_parse_user_mapper(self):
        mp = FakeMapper(source='host.process.guid', edge='has_user', target='sysmon.user')
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        p = self._parser(mappers=[mp], used_facts=[fact])
        event = 'User: DOMAIN\\user1'
        result = p.parse(event)
        assert len(result) == 1
        assert result[0].target.value == 'DOMAIN\\user1'

    def test_parse_empty_blob(self):
        mp = FakeMapper(source='s', edge='e', target='sysmon.eventid')
        fact = FakeFact(trait='s', value='v')
        p = self._parser(mappers=[mp], used_facts=[fact])
        result = p.parse('')
        assert result == []

    def test_parse_multiple_mappers(self):
        mp1 = FakeMapper(source='host.process.guid', edge='e1', target='sysmon.eventid')
        mp2 = FakeMapper(source='host.process.guid', edge='e2', target='sysmon.recordid')
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        p = self._parser(mappers=[mp1, mp2], used_facts=[fact])
        event = 'Id : 1\r\nRecordId : 2'
        result = p.parse(event)
        assert len(result) == 2
