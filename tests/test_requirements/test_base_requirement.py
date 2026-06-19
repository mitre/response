"""Tests for app.requirements.base_requirement."""
import sys
sys.path.insert(0, '/tmp/response-pytest')

from tests.conftest import FakeFact, FakeRelationship
from app.requirements.base_requirement import BaseRequirement


class TestBaseRequirement:

    def _req(self, enforcements):
        return BaseRequirement({'enforcements': enforcements})

    # ── _check_edge ──────────────────────────────────────────────────────

    def test_check_edge_match(self):
        req = self._req({'edge': 'has_property'})
        assert req._check_edge('has_property') is True

    def test_check_edge_mismatch(self):
        req = self._req({'edge': 'has_property'})
        assert req._check_edge('other_edge') is False

    # ── _check_target ────────────────────────────────────────────────────

    def test_check_target_match(self):
        target = FakeFact(trait='t', value='v')
        match = FakeFact(trait='t', value='v')
        assert BaseRequirement._check_target(target, match) is True

    def test_check_target_mismatch_trait(self):
        target = FakeFact(trait='t1', value='v')
        match = FakeFact(trait='t2', value='v')
        assert BaseRequirement._check_target(target, match) is False

    def test_check_target_mismatch_value(self):
        target = FakeFact(trait='t', value='v1')
        match = FakeFact(trait='t', value='v2')
        assert BaseRequirement._check_target(target, match) is False

    # ── _get_relationships ───────────────────────────────────────────────

    def test_get_relationships_filters_correctly(self):
        uf = FakeFact(trait='host.process.id', value='100')
        r1 = FakeRelationship(source=FakeFact(trait='host.process.id', value='100'), edge='e')
        r2 = FakeRelationship(source=FakeFact(trait='other', value='100'), edge='e')
        r3 = FakeRelationship(source=FakeFact(trait='host.process.id', value='999'), edge='e')
        result = BaseRequirement._get_relationships(uf, [r1, r2, r3])
        assert result == [r1]

    def test_get_relationships_empty(self):
        uf = FakeFact(trait='t', value='v')
        assert BaseRequirement._get_relationships(uf, []) == []

    # ── is_valid_relationship ────────────────────────────────────────────

    def test_is_valid_wrong_edge(self):
        req = self._req({'edge': 'has_x'})
        rel = FakeRelationship(edge='has_y')
        assert req.is_valid_relationship([], rel) is False

    def test_is_valid_no_target_enforcement(self):
        req = self._req({'edge': 'has_x'})
        rel = FakeRelationship(edge='has_x')
        assert req.is_valid_relationship([], rel) is True

    def test_is_valid_target_enforcement_match(self):
        req = self._req({'edge': 'has_x', 'target': 'tgt.trait'})
        rel = FakeRelationship(
            edge='has_x',
            target=FakeFact(trait='tgt.trait', value='v1'),
        )
        used_fact = FakeFact(trait='tgt.trait', value='v1')
        assert req.is_valid_relationship([used_fact], rel) is True

    def test_is_valid_target_enforcement_no_match(self):
        req = self._req({'edge': 'has_x', 'target': 'tgt.trait'})
        rel = FakeRelationship(
            edge='has_x',
            target=FakeFact(trait='tgt.trait', value='v1'),
        )
        used_fact = FakeFact(trait='tgt.trait', value='DIFFERENT')
        assert req.is_valid_relationship([used_fact], rel) is False

    def test_is_valid_target_enforcement_no_facts(self):
        req = self._req({'edge': 'has_x', 'target': 'tgt.trait'})
        rel = FakeRelationship(
            edge='has_x',
            target=FakeFact(trait='tgt.trait', value='v1'),
        )
        assert req.is_valid_relationship([], rel) is False
