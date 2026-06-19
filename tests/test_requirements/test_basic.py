"""Tests for app.requirements.basic."""
import sys
import pytest
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeFact, FakeRelationship, FakeLink, FakeOperation
from app.requirements.basic import Requirement


class TestBasicRequirement:

    def _req(self, enforcements):
        return Requirement({'enforcements': enforcements})

    @pytest.mark.asyncio
    async def test_enforce_returns_true_on_valid_match(self):
        req = self._req({'source': 'host.process.id', 'edge': 'has_port'})
        uf = FakeFact(trait='host.process.id', value='100')
        link = FakeLink(used=[uf])
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.id', value='100'),
            edge='has_port',
            target=FakeFact(trait='host.port', value='80'),
        )
        op = FakeOperation(relationships=[rel])
        assert await req.enforce(link, op) is True

    @pytest.mark.asyncio
    async def test_enforce_returns_false_no_source_match(self):
        req = self._req({'source': 'host.process.id', 'edge': 'has_port'})
        uf = FakeFact(trait='other.trait', value='100')
        link = FakeLink(used=[uf])
        op = FakeOperation(relationships=[])
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_wrong_edge(self):
        req = self._req({'source': 'host.process.id', 'edge': 'has_port'})
        uf = FakeFact(trait='host.process.id', value='100')
        link = FakeLink(used=[uf])
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.id', value='100'),
            edge='wrong_edge',
        )
        op = FakeOperation(relationships=[rel])
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_with_target_enforcement(self):
        req = self._req({'source': 'host.process.id', 'edge': 'has_port', 'target': 'host.port'})
        uf1 = FakeFact(trait='host.process.id', value='100')
        uf2 = FakeFact(trait='host.port', value='80')
        link = FakeLink(used=[uf1, uf2])
        rel = FakeRelationship(
            source=FakeFact(trait='host.process.id', value='100'),
            edge='has_port',
            target=FakeFact(trait='host.port', value='80'),
        )
        op = FakeOperation(relationships=[rel])
        assert await req.enforce(link, op) is True

    @pytest.mark.asyncio
    async def test_enforce_returns_false_empty_used(self):
        req = self._req({'source': 'host.process.id', 'edge': 'has_port'})
        link = FakeLink(used=[])
        op = FakeOperation()
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_no_relationships(self):
        req = self._req({'source': 'host.process.id', 'edge': 'has_port'})
        uf = FakeFact(trait='host.process.id', value='100')
        link = FakeLink(used=[uf])
        op = FakeOperation(relationships=[])
        assert await req.enforce(link, op) is False
