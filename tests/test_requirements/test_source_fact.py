"""Tests for app.requirements.source_fact."""
import sys
import pytest
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeFact, FakeLink, FakeOperation, FakeSource
from app.requirements.source_fact import Requirement


class TestSourceFactRequirement:

    def _req(self, enforcements):
        return Requirement({'enforcements': enforcements})

    @pytest.mark.asyncio
    async def test_enforce_returns_true_when_fact_in_source(self):
        req = self._req({'source': 'host.process.id', 'edge': 'e'})
        uf = FakeFact(trait='host.process.id', value='100')
        link = FakeLink(used=[uf])
        source = FakeSource(facts=[FakeFact(trait='host.process.id', value='100')])
        op = FakeOperation(source=source)
        assert await req.enforce(link, op) is True

    @pytest.mark.asyncio
    async def test_enforce_returns_false_when_fact_not_in_source(self):
        req = self._req({'source': 'host.process.id', 'edge': 'e'})
        uf = FakeFact(trait='host.process.id', value='100')
        link = FakeLink(used=[uf])
        source = FakeSource(facts=[FakeFact(trait='host.process.id', value='999')])
        op = FakeOperation(source=source)
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_wrong_trait(self):
        req = self._req({'source': 'host.process.id', 'edge': 'e'})
        uf = FakeFact(trait='other.trait', value='100')
        link = FakeLink(used=[uf])
        source = FakeSource(facts=[FakeFact(trait='host.process.id', value='100')])
        op = FakeOperation(source=source)
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_empty_used(self):
        req = self._req({'source': 'host.process.id', 'edge': 'e'})
        link = FakeLink(used=[])
        source = FakeSource(facts=[FakeFact(trait='host.process.id', value='100')])
        op = FakeOperation(source=source)
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_returns_false_empty_source_facts(self):
        req = self._req({'source': 'host.process.id', 'edge': 'e'})
        uf = FakeFact(trait='host.process.id', value='100')
        link = FakeLink(used=[uf])
        source = FakeSource(facts=[])
        op = FakeOperation(source=source)
        assert await req.enforce(link, op) is False

    @pytest.mark.asyncio
    async def test_enforce_multiple_used_facts(self):
        req = self._req({'source': 'host.process.id', 'edge': 'e'})
        uf1 = FakeFact(trait='other', value='x')
        uf2 = FakeFact(trait='host.process.id', value='42')
        link = FakeLink(used=[uf1, uf2])
        source = FakeSource(facts=[FakeFact(trait='host.process.id', value='42')])
        op = FakeOperation(source=source)
        assert await req.enforce(link, op) is True
