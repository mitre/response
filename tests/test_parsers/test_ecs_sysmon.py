"""Tests for app.parsers.ecs_sysmon."""
import sys
import json
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeMapper, FakeFact
from app.parsers.ecs_sysmon import Parser


def _event(overrides=None):
    """Build a minimal ECS-style sysmon event dict."""
    base = {
        '_id': 'es-id-1',
        '_source': {
            'process': {
                'entity_id': '{guid-123}',
                'pid': 42,
                'name': 'cmd.exe',
                'parent': {
                    'entity_id': '{parent-guid-456}',
                },
            },
            'winlog': {
                'event_id': 1,
                'record_id': 999,
            },
            'user': {
                'domain': 'CORP',
                'name': 'admin',
            },
        },
    }
    if overrides:
        base.update(overrides)
    return base


class TestEcsSysmonParser:

    def _parser(self, mappers=None, used_facts=None):
        p = Parser.__new__(Parser)
        p.mappers = mappers or []
        p.used_facts = used_facts or []
        return p

    # ── Individual parse methods ─────────────────────────────────────────

    def test_parse_process_guid(self):
        event = _event()
        assert Parser.parse_process_guid(event) == 'guid-123'

    def test_parse_parent_process_guid(self):
        event = _event()
        assert Parser.parse_parent_process_guid(event) == 'parent-guid-456'

    def test_parse_eventid(self):
        assert Parser.parse_eventid(_event()) == 1

    def test_parse_recordid(self):
        assert Parser.parse_recordid(_event()) == 999

    def test_parse_user(self):
        assert Parser.parse_user(_event()) == 'CORP\\admin'

    def test_parse_pid(self):
        assert Parser.parse_pid(_event()) == 42

    def test_parse_pid_missing(self):
        event = {'_source': {}}
        assert Parser.parse_pid(event) is None

    def test_parse_process_name(self):
        assert Parser.parse_process_name(_event()) == 'cmd.exe'

    # ── flatten_dict ─────────────────────────────────────────────────────

    def test_flatten_dict_simple(self):
        result = Parser.flatten_dict({'a': 1, 'b': 2})
        assert result == {'a': 1, 'b': 2}

    def test_flatten_dict_nested(self):
        result = Parser.flatten_dict({'a': {'b': {'c': 3}}})
        assert result == {'a.b.c': 3}

    def test_flatten_dict_empty(self):
        assert Parser.flatten_dict({}) == {}

    def test_flatten_dict_mixed(self):
        result = Parser.flatten_dict({'x': 1, 'y': {'z': 2}})
        assert result == {'x': 1, 'y.z': 2}

    # ── _sanitize_fact_traits ────────────────────────────────────────────

    def test_sanitize_removes_special_chars(self):
        assert Parser._sanitize_fact_traits('@key[0]') == 'key0'

    def test_sanitize_removes_slashes(self):
        assert Parser._sanitize_fact_traits('a/b\\c') == 'abc'

    def test_sanitize_removes_quotes(self):
        # The source contains two ASCII double-quote entries in special_chars
        assert Parser._sanitize_fact_traits('"test"') == 'test'

    def test_sanitize_removes_at_and_brackets(self):
        assert Parser._sanitize_fact_traits('@test[0]') == 'test0'

    def test_sanitize_no_special(self):
        assert Parser._sanitize_fact_traits('clean.trait') == 'clean.trait'

    # ── parse_elasticsearch_results ──────────────────────────────────────

    def test_parse_elasticsearch_results(self):
        event = _event()
        rels = Parser.parse_elasticsearch_results(event)
        # Should have relationships for flattened source keys + a pid relationship
        assert len(rels) > 0
        # Check that elasticsearch.result.id is used as source
        es_rels = [r for r in rels if r.source.trait == 'elasticsearch.result.id']
        assert len(es_rels) > 0
        assert es_rels[0].source.value == 'es-id-1'
        # Check pid relationship
        pid_rels = [r for r in rels if r.source.trait == 'host.process.id']
        assert len(pid_rels) == 1
        assert pid_rels[0].source.value == 42

    def test_parse_elasticsearch_results_no_pid(self):
        event = {'_id': 'x', '_source': {'key': 'val'}}
        rels = Parser.parse_elasticsearch_results(event)
        pid_rels = [r for r in rels if r.source.trait == 'host.process.id']
        assert len(pid_rels) == 0

    # ── parse (main method) ──────────────────────────────────────────────

    def test_parse_dict_event_with_mapper(self):
        mp = FakeMapper(source='host.process.guid', edge='has_eventid', target='sysmon.eventid')
        p = self._parser(mappers=[mp])
        event = _event()
        blob = json.dumps(event)
        result = p.parse(blob)
        # Should have mapper relationships + elasticsearch relationships
        assert len(result) > 0

    def test_parse_array_returns_empty(self):
        """Arrays should not be parsed (they are handled by pseudo-links)."""
        mp = FakeMapper(source='s', edge='e', target='sysmon.eventid')
        p = self._parser(mappers=[mp])
        blob = json.dumps([_event(), _event()])
        result = p.parse(blob)
        assert result == []

    def test_parse_options_keys(self):
        p = self._parser()
        opts = p.parse_options
        expected = {'eventid', 'recordid', 'user', 'guid', 'pid', 'name', 'parent_guid'}
        assert set(opts.keys()) == expected

    def test_parse_with_bad_mapper_logs_debug(self):
        """A mapper targeting a non-existent parse option should not crash."""
        mp = FakeMapper(source='s', edge='e', target='sysmon.nonexistent')
        p = self._parser(mappers=[mp])
        event = _event()
        blob = json.dumps(event)
        # Should not raise
        result = p.parse(blob)
        # Still gets elasticsearch relationships
        assert any(r.source.trait == 'elasticsearch.result.id' for r in result)
