"""Tests for response_svc.py — ResponseService and module-level helpers."""
import sys
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import (
    FakeFact, FakeRelationship, FakeLink, FakeOperation, FakeAgent, FakeSource,
)
from app.response_svc import ResponseService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svc(overrides=None):
    """Build a ResponseService backed by mocks."""
    services = {
        'data_svc': MagicMock(),
        'rest_svc': MagicMock(),
        'app_svc': MagicMock(),
        'file_svc': MagicMock(),
        'event_svc': MagicMock(),
    }
    if overrides:
        services.update(overrides)
    svc = ResponseService(services)
    return svc


# ── Static / pure helpers ────────────────────────────────────────────────────

class TestFilterAbilityFacts:

    def test_passthrough_for_other_traits(self):
        svc = _svc()
        fact = FakeFact(trait='host.something', value='v')
        result = svc._filter_ability_facts([fact], [], '111', '222')
        assert result == [fact]

    def test_host_process_guid_included_when_child(self):
        svc = _svc()
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.guid', value='guid-1'),
            edge='has_parentid',
            target=FakeFact(trait='host.process.id', value='111'),
        )
        result = svc._filter_ability_facts([fact], [rel], '111', '222')
        assert fact in result

    def test_host_process_guid_excluded_when_not_child(self):
        svc = _svc()
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        result = svc._filter_ability_facts([fact], [], '111', '222')
        assert fact not in result

    def test_host_process_parentguid_included_when_red_guid(self):
        svc = _svc()
        fact = FakeFact(trait='host.process.parentguid', value='red-guid')
        rel = FakeRelationship(
            source=FakeFact(trait='x', value='111'),
            edge='has_guid',
            target=FakeFact(trait='y', value='red-guid'),
        )
        result = svc._filter_ability_facts([fact], [rel], '111', '222')
        assert fact in result


class TestIsChildGuid:

    def test_returns_true_on_match_red_pid(self):
        rel = FakeRelationship(
            source=FakeFact(trait='x', value='guid-1'),
            edge='has_parentid',
            target=FakeFact(trait='y', value='111'),
        )
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        assert ResponseService._is_child_guid([rel], '111', '222', fact)

    def test_returns_true_on_match_original_pid(self):
        rel = FakeRelationship(
            source=FakeFact(trait='x', value='guid-1'),
            edge='has_parentid',
            target=FakeFact(trait='y', value='222'),
        )
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        assert ResponseService._is_child_guid([rel], '111', '222', fact)

    def test_returns_false_when_no_match(self):
        fact = FakeFact(trait='host.process.guid', value='guid-1')
        assert not ResponseService._is_child_guid([], '111', '222', fact)


class TestIsRedAgentGuid:

    def test_returns_true_when_guid_matches(self):
        rel = FakeRelationship(
            source=FakeFact(trait='x', value='111'),
            edge='has_guid',
            target=FakeFact(trait='y', value='red-guid'),
        )
        fact = FakeFact(trait='host.process.parentguid', value='red-guid')
        assert ResponseService._is_red_agent_guid([rel], '111', fact)

    def test_returns_false_when_guid_differs(self):
        rel = FakeRelationship(
            source=FakeFact(trait='x', value='111'),
            edge='has_guid',
            target=FakeFact(trait='y', value='red-guid'),
        )
        fact = FakeFact(trait='host.process.parentguid', value='other-guid')
        assert not ResponseService._is_red_agent_guid([rel], '111', fact)


class TestGetOriginalGuid:

    @pytest.mark.asyncio
    async def test_returns_guid_on_match(self):
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.id', value='100'),
            edge='has_guid',
            target=FakeFact(trait='host.process.guid', value='the-guid'),
        )
        result = await ResponseService._get_original_guid('100', [rel])
        assert result == 'the-guid'

    @pytest.mark.asyncio
    async def test_returns_none_when_no_match(self):
        result = await ResponseService._get_original_guid('100', [])
        assert result is None

    @pytest.mark.asyncio
    async def test_ignores_wrong_trait(self):
        rel = FakeRelationship(
            source=FakeFact(trait='wrong.trait', value='100'),
            edge='has_guid',
            target=FakeFact(trait='host.process.guid', value='the-guid'),
        )
        result = await ResponseService._get_original_guid('100', [rel])
        assert result is None

    @pytest.mark.asyncio
    async def test_ignores_wrong_edge(self):
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.id', value='100'),
            edge='wrong_edge',
            target=FakeFact(trait='host.process.guid', value='the-guid'),
        )
        result = await ResponseService._get_original_guid('100', [rel])
        assert result is None


class TestGetInfoFromTopLevelProcessLink:

    @pytest.mark.asyncio
    async def test_extracts_pid_and_guid(self):
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.id', value=' 42 '),
            edge='has_guid',
            target=FakeFact(trait='host.process.guid', value='guid-x'),
        )
        link = FakeLink(relationships=[rel])
        pid, guid, parent_guid = await ResponseService.get_info_from_top_level_process_link(link)
        assert pid == 42
        assert guid == 'guid-x'
        assert parent_guid is None

    @pytest.mark.asyncio
    async def test_returns_nones_for_empty_link(self):
        link = FakeLink(relationships=[])
        pid, guid, parent_guid = await ResponseService.get_info_from_top_level_process_link(link)
        assert pid is None
        assert guid is None
        assert parent_guid is None


class TestGetInfoFromChildProcessLink:

    @pytest.mark.asyncio
    async def test_extracts_all_fields(self):
        rel_id = FakeRelationship(
            source=FakeFact(trait='host.process.guid', value='parent-guid'),
            edge='has_childprocess_id',
            target=FakeFact(trait='host.process.id', value=' 99 '),
        )
        rel_guid = FakeRelationship(
            source=FakeFact(trait='host.process.guid', value='parent-guid'),
            edge='has_childprocess_guid',
            target=FakeFact(trait='host.process.guid', value='child-guid'),
        )
        link = FakeLink(relationships=[rel_id, rel_guid])
        pid, guid, parent_guid = await ResponseService.get_info_from_child_process_link(link)
        assert pid == 99
        assert guid == 'child-guid'
        assert parent_guid == 'parent-guid'

    @pytest.mark.asyncio
    async def test_returns_nones_for_empty_link(self):
        link = FakeLink(relationships=[])
        pid, guid, parent_guid = await ResponseService.get_info_from_child_process_link(link)
        assert pid is None
        assert guid is None
        assert parent_guid is None


class TestCreateFactSource:

    @pytest.mark.asyncio
    async def test_returns_source_with_unique_name(self):
        s = await ResponseService.create_fact_source()
        assert s.name.startswith('blue-pid-')
        assert s.facts == []


class TestWaitForLinkCompletion:

    @pytest.mark.asyncio
    async def test_returns_immediately_when_finished(self):
        link = FakeLink(finish=True)
        agent = FakeAgent()
        await ResponseService.wait_for_link_completion([link], agent)

    @pytest.mark.asyncio
    async def test_returns_when_agent_untrusted(self):
        link = FakeLink(finish=None)
        agent = FakeAgent(trusted=False)
        await ResponseService.wait_for_link_completion([link], agent)


class TestGetAvailableAgents:

    @pytest.mark.asyncio
    async def test_returns_agents_on_same_host(self):
        svc = _svc()
        blue_agent = FakeAgent(host='h1')
        svc.agents = [blue_agent]
        svc.adversary = MagicMock()
        svc.adversary.atomic_ordering = []
        svc.data_svc = AsyncMock()
        svc.data_svc.locate = AsyncMock(return_value=[blue_agent])
        svc.apply_adversary_config = AsyncMock()
        red = FakeAgent(host='h1')
        result = await svc.get_available_agents(red)
        assert result == [blue_agent]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_match(self):
        svc = _svc()
        svc.agents = []
        svc.adversary = MagicMock()
        svc.adversary.atomic_ordering = []
        svc.data_svc = AsyncMock()
        svc.data_svc.locate = AsyncMock(return_value=[])
        svc.apply_adversary_config = AsyncMock()
        red = FakeAgent(host='h1')
        result = await svc.get_available_agents(red)
        assert result == []


class TestRespondToPid:

    @pytest.mark.asyncio
    async def test_noop_when_no_agents(self):
        svc = _svc()
        svc.get_available_agents = AsyncMock(return_value=[])
        red = FakeAgent()
        result = await svc.respond_to_pid('123', red, 'visible')
        assert result is None

    @pytest.mark.asyncio
    async def test_creates_operation_when_none_exists(self):
        svc = _svc()
        blue = FakeAgent(host='h1')
        svc.get_available_agents = AsyncMock(return_value=[blue])
        svc.create_fact_source = AsyncMock(return_value=FakeSource())
        svc.create_operation = AsyncMock()
        svc.run_abilities_on_agent = AsyncMock(return_value=([], []))
        svc.ops = {}
        red = FakeAgent(host='h1', pid=100)
        await svc.respond_to_pid('123', red, 'visible')
        svc.create_operation.assert_awaited_once()


class TestProcessChildProcessLinks:

    @pytest.mark.asyncio
    async def test_extracts_child_guids(self):
        svc = _svc()
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.guid', value='pg'),
            edge='has_childprocess_guid',
            target=FakeFact(trait='host.process.guid', value='cg'),
        )
        link = FakeLink(relationships=[rel])
        svc.add_link_to_process_tree = AsyncMock()
        result = await svc.process_child_process_links([link])
        assert 'cg' in result

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_match(self):
        svc = _svc()
        link = FakeLink(relationships=[])
        svc.add_link_to_process_tree = AsyncMock()
        result = await svc.process_child_process_links([link])
        assert result == []


class TestRegisterHandler:

    @pytest.mark.asyncio
    async def test_registers_event(self):
        event_svc = MagicMock()
        event_svc.observe_event = AsyncMock()
        await ResponseService.register_handler(event_svc)
        event_svc.observe_event.assert_awaited_once()


class TestUpdateOperation:

    @pytest.mark.asyncio
    async def test_links_added_to_op(self):
        svc = _svc()
        op = MagicMock()
        op.id = 'op-1'
        op.add_link = MagicMock()
        svc.ops = {'visible': op}
        link = FakeLink()
        await svc.update_operation([link], 'visible')
        assert link.operation == 'op-1'
        op.add_link.assert_called_once_with(link)
