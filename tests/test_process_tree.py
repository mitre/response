"""Tests for ProcessNode and ProcessTree."""
import sys
import pytest

sys.path.insert(0, '/tmp/response-pytest')

from app.c_processnode import ProcessNode
from app.c_processtree import ProcessTree
from tests.conftest import FakeLink


# ── ProcessNode ──────────────────────────────────────────────────────────────

class TestProcessNode:

    def test_init_defaults(self):
        link = FakeLink()
        node = ProcessNode(pid=100, link=link)
        assert node.pid == 100
        assert node.link is link
        assert node.parent_guid is None
        assert node.child_guids == []

    def test_init_with_parent_and_children(self):
        link = FakeLink()
        node = ProcessNode(pid=200, link=link, parent_guid='pg1', child_guids=['c1', 'c2'])
        assert node.parent_guid == 'pg1'
        assert node.child_guids == ['c1', 'c2']

    def test_add_child_same_host(self):
        link = FakeLink(host='h1')
        node = ProcessNode(pid=1, link=link)
        child_link = FakeLink(host='h1')
        node.add_child('child-guid-1', child_link)
        assert 'child-guid-1' in node.child_guids

    def test_add_child_different_host_rejected(self):
        link = FakeLink(host='h1')
        node = ProcessNode(pid=1, link=link)
        child_link = FakeLink(host='h2')
        node.add_child('child-guid-2', child_link)
        assert 'child-guid-2' not in node.child_guids

    def test_add_child_no_duplicates(self):
        link = FakeLink(host='h1')
        node = ProcessNode(pid=1, link=link)
        child_link = FakeLink(host='h1')
        node.add_child('g1', child_link)
        node.add_child('g1', child_link)
        assert node.child_guids.count('g1') == 1

    def test_child_guids_not_shared_across_instances(self):
        link = FakeLink()
        n1 = ProcessNode(pid=1, link=link)
        n2 = ProcessNode(pid=2, link=link)
        n1.add_child('g', FakeLink(host=link.host))
        assert n2.child_guids == []


# ── ProcessTree ──────────────────────────────────────────────────────────────

class TestProcessTree:

    def _tree(self, host='host1', ptree_id=42):
        return ProcessTree(host=host, ptree_id=ptree_id)

    def test_init_defaults(self):
        t = ProcessTree('myhost')
        assert t.host == 'myhost'
        assert isinstance(t.ptree_id, int)
        assert t.pid_to_guids_map == {}
        assert t.guid_to_processnode_map == {}

    def test_unique_property(self):
        t = self._tree()
        assert t.unique == 'host142'

    @pytest.mark.asyncio
    async def test_add_processnode_basic(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='g1', pid=100, link=link)
        assert 'g1' in t.guid_to_processnode_map
        assert 100 in t.pid_to_guids_map
        assert 'g1' in t.pid_to_guids_map[100]

    @pytest.mark.asyncio
    async def test_add_processnode_with_parent(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='parent-g', pid=10, link=link)
        await t.add_processnode(guid='child-g', pid=20, link=link, parent_guid='parent-g')
        parent_node = t.guid_to_processnode_map['parent-g']
        assert 'child-g' in parent_node.child_guids

    @pytest.mark.asyncio
    async def test_add_multiple_guids_for_same_pid(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='g1', pid=100, link=link)
        await t.add_processnode(guid='g2', pid=100, link=link)
        assert t.pid_to_guids_map[100] == ['g1', 'g2']

    @pytest.mark.asyncio
    async def test_find_parent_guid_exists(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='parent-g', pid=10, link=link)
        await t.add_processnode(guid='child-g', pid=20, link=link, parent_guid='parent-g')
        assert await t.find_parent_guid('child-g') == 'parent-g'

    @pytest.mark.asyncio
    async def test_find_parent_guid_none(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='g1', pid=10, link=link)
        assert await t.find_parent_guid('g1') is None

    @pytest.mark.asyncio
    async def test_find_parent_guid_missing_guid(self):
        t = self._tree()
        assert await t.find_parent_guid('nonexistent') is None

    @pytest.mark.asyncio
    async def test_convert_guids_to_pids(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='g1', pid=10, link=link)
        await t.add_processnode(guid='g2', pid=20, link=link)
        pids = await t.convert_guids_to_pids(['g1', 'g2'])
        assert pids == [10, 20]

    @pytest.mark.asyncio
    async def test_convert_guids_to_pids_empty(self):
        t = self._tree()
        assert await t.convert_guids_to_pids([]) == []

    @pytest.mark.asyncio
    async def test_find_original_processes_single_chain(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='root', pid=1, link=link)
        await t.add_processnode(guid='mid', pid=2, link=link, parent_guid='root')
        await t.add_processnode(guid='leaf', pid=3, link=link, parent_guid='mid')
        original = await t.find_original_processes_by_pid(3)
        assert original == [1]

    @pytest.mark.asyncio
    async def test_find_original_processes_no_parent(self):
        t = self._tree()
        link = FakeLink(host='host1')
        await t.add_processnode(guid='g1', pid=10, link=link)
        original = await t.find_original_processes_by_pid(10)
        assert original == [10]

    @pytest.mark.asyncio
    async def test_find_original_processes_unknown_pid(self):
        t = self._tree()
        original = await t.find_original_processes_by_pid(999)
        assert original == []

    @pytest.mark.asyncio
    async def test_find_original_multiple_guids_same_pid(self):
        t = self._tree()
        link = FakeLink(host='host1')
        # Two separate roots both mapping to pid 5
        await t.add_processnode(guid='r1', pid=5, link=link)
        await t.add_processnode(guid='r2', pid=5, link=link)
        # Child of r1
        await t.add_processnode(guid='c1', pid=10, link=link, parent_guid='r1')
        original = await t.find_original_processes_by_pid(10)
        assert original == [5]

    def test_store_adds_to_ram(self):
        t = self._tree()
        ram = {'processtrees': []}
        result = t.store(ram)
        assert len(ram['processtrees']) == 1
        assert result is t

    def test_store_no_duplicate(self):
        t = self._tree()
        ram = {'processtrees': []}
        t.store(ram)
        t.store(ram)
        assert len(ram['processtrees']) == 1

    def test_store_returns_existing(self):
        t = self._tree()
        ram = {'processtrees': []}
        first = t.store(ram)
        second = t.store(ram)
        assert first is second
