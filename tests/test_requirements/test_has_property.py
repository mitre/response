"""Tests for app.requirements.has_property."""
import sys
import pytest
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeFact, FakeRelationship, FakeLink, FakeOperation
from app.requirements.has_property import Requirement


class TestHasPropertyRequirement:

    def _req(self, enforcements):
        return Requirement({'enforcements': enforcements})

    @pytest.mark.asyncio
    async def test_enforce_returns_true_when_property_present(self):
        req = self._req({
            'source': 'elasticsearch.result.id',
            'edge': 'has_property',
            'target': 'process.name',
        })
        uf = FakeFact(trait='elasticsearch.result.id', value='es-1')
        link = FakeLink(used=[uf])
        rel = FakeRelationship(
            source=FakeFact(trait='elasticsearch.result.id', value='es-1'),
            edge='has_property',
            target=FakeFact(trait='process.name', value='cmd.exe'),
        )
        op = FakeOperation(relationships=[rel])
        assert await req.enforce(link, op) is True

    @pytest.mark.asyncio
    async def test_enforce_returns_false_wrong_edge(self):
        req = self._req({
            'source': 'elasticsearch.result.id',
            'edge': 'has_property',
            'target': 'process.name',
        })
        uf = FakeFact(trait='elasticsearch.result.id', value='es-1')
        link = FakeLink(used=[uf])
        rel = FakeRelationship(
            source=FakeFact(trait='elasticsearch.result.id', value='es-1'),
            edge='other_edge',
            target=FakeFact(trait='process.name', value='cmd.exe'),
        )
        op = FakeOperation(relationships=[rel])
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_wrong_target_trait(self):
        req = self._req({
            'source': 'elasticsearch.result.id',
            'edge': 'has_property',
            'target': 'process.name',
        })
        uf = FakeFact(trait='elasticsearch.result.id', value='es-1')
        link = FakeLink(used=[uf])
        rel = FakeRelationship(
            source=FakeFact(trait='elasticsearch.result.id', value='es-1'),
            edge='has_property',
            target=FakeFact(trait='wrong.trait', value='cmd.exe'),
        )
        op = FakeOperation(relationships=[rel])
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_no_source_match(self):
        req = self._req({
            'source': 'elasticsearch.result.id',
            'edge': 'has_property',
            'target': 'process.name',
        })
        uf = FakeFact(trait='other.trait', value='es-1')
        link = FakeLink(used=[uf])
        op = FakeOperation(relationships=[])
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_empty_used(self):
        req = self._req({
            'source': 'elasticsearch.result.id',
            'edge': 'has_property',
            'target': 'process.name',
        })
        link = FakeLink(used=[])
        op = FakeOperation()
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_no_matching_relationship(self):
        req = self._req({
            'source': 'elasticsearch.result.id',
            'edge': 'has_property',
            'target': 'process.name',
        })
        uf = FakeFact(trait='elasticsearch.result.id', value='es-1')
        link = FakeLink(used=[uf])
        op = FakeOperation(relationships=[])
        assert await req.enforce(link, op) is False
