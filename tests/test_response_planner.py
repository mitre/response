import pytest

from app.objects.c_ability import Ability
from app.objects.c_adversary import Adversary
from app.utility.base_world import BaseWorld
from app.objects.secondclass.c_fact import Fact
from app.objects.secondclass.c_link import Link
from app.objects.c_obfuscator import Obfuscator
from app.objects.c_operation import Operation
from app.objects.secondclass.c_relationship import Relationship
from app.objects.c_source import Source

from plugins.response.app.response_planner import LogicalPlanner as ResponsePlanner


def create_abilities(tactic, count):
    abilities = []
    atomic_ordering = []
    for i in range(count):
        abilities.append(Ability(ability_id=tactic+str(i), tactic=tactic, executor='sh', platform='linux',
                                 test=BaseWorld.encode_string(tactic+str(i))))
        atomic_ordering.append(tactic+str(i))
    return abilities, atomic_ordering

@pytest.fixture
def setup_planner_test(loop, agent, data_svc, init_base_world):
    abilities = dict()
    atomic_ordering = []
    for tactic in ['detection', 'hunt', 'response']:
        abilities[tactic], ao = create_abilities(tactic, 3)
        atomic_ordering.extend(ao)
    tagent = agent(sleep_min=1, sleep_max=2, watchdog=0, executors=['sh'], platform='linux')
    tsource = Source(id='123', name='test', facts=[], adjustments=[])
    toperation = Operation(name='test1', agents=[tagent], adversary=Adversary(name='test', description='test',
                                                                              atomic_ordering=atomic_ordering,
                                                                              adversary_id='XYZ'),
                           source=tsource)

    for a in [ab for ab in abilities[tactic] for tactic in abilities]:
        loop.run_until_complete(data_svc.store(a))

    loop.run_until_complete(data_svc.store(
        Obfuscator(name='plain-text',
                   description='Does no obfuscation to any command, instead running it in plain text',
                   module='plugins.stockpile.app.obfuscators.plain_text')
    ))

    yield abilities, tagent, toperation


class TestResponsePlanner:

    @pytest.mark.skip
    async def setup_mock_execute_links(self, planner, operation, link_ids, condition_stop):
        return

    def test_do_reactive_bucket(self, loop, mocker, setup_planner_test, planning_svc, capsys):
        """
        This one needs to test the ability to look for unaddressed parent links, and mark these parents as addressed.
        """
        mocker.patch.object(planning_svc, 'execute_links', new=self.setup_mock_execute_links)
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        test_rel1 = Relationship(source=test_fact1)
        test_rel2 = Relationship(source=test_fact1, edge='test_edge', target=test_fact2)
        link1 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link2 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link3 = Link(command=ability.test, paw=agent.paw, ability=ability)

        loop.run_until_complete(planner._do_reactive_bucket('hunt'))
        captured = capsys.readouterr()
        print(captured.out)
        print(captured.err)
        assert len(operation.chain) == 3

    def test_run_links(self, loop, mocker, setup_planner_test, planning_svc):
        mocker.patch.object(planning_svc, 'execute_links', new=self.setup_mock_execute_links)
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        test_rel1 = Relationship(source=test_fact1)
        test_rel2 = Relationship(source=test_fact1, edge='test_edge', target=test_fact2)
        link1 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link2 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link3 = Link(command=ability.test, paw=agent.paw, ability=ability)

        loop.run_until_complete(planner._run_links([link1]))
        assert len(operation.chain) == 1
        assert link1 in operation.chain

        loop.run_until_complete(planner._run_links([link2, link3]))
        assert len(operation.chain) == 3
        assert link2 in operation.chain
        assert link3 in operation.chain

    def test_get_link_storage(self, setup_planner_test, planning_svc):
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        link1 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link2 = Link(command=ability.test, paw=agent.paw, ability=ability)

        planner.links_hunted.add(link1)
        planner.links_responded.add(link2)

        assert link1 in planner._get_link_storage('hunt')
        assert link2 in planner._get_link_storage('response')

    def test_get_unaddressed_parent_links(self, setup_planner_test, planning_svc):
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        test_rel1 = Relationship(source=test_fact1)
        test_rel2 = Relationship(source=test_fact1, edge='test_edge', target=test_fact2)
        link1 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link2 = Link(command=ability.test, paw=agent.paw, ability=ability)
        operation.chain.extend([link1, link2])

        link3 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link3.used.extend([test_fact1, test_fact2])

        assert not len(planner._get_unaddressed_parent_links(link3, planner.links_hunted))

        link1.relationships.append(test_rel1)
        assert len(planner._get_unaddressed_parent_links(link3, planner.links_hunted)) == 1
        assert link1 in planner._get_unaddressed_parent_links(link3, planner.links_hunted)

        link2.relationships.append(test_rel2)
        assert len(planner._get_unaddressed_parent_links(link3, planner.links_hunted)) == 2
        assert link1 in planner._get_unaddressed_parent_links(link3, planner.links_hunted)
        assert link2 in planner._get_unaddressed_parent_links(link3, planner.links_hunted)

        planner.links_hunted.add(link1)
        assert len(planner._get_unaddressed_parent_links(link3, planner.links_hunted)) == 1
        assert link2 in planner._get_unaddressed_parent_links(link3, planner.links_hunted)

        planner.links_hunted.add(link2)
        assert not len(planner._get_unaddressed_parent_links(link3, planner.links_hunted))

    def test_get_parent_links(self, setup_planner_test, planning_svc):
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        test_rel1 = Relationship(source=test_fact1)
        test_rel2 = Relationship(source=test_fact1, edge='test_edge', target=test_fact2)
        link1 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link2 = Link(command=ability.test, paw=agent.paw, ability=ability)
        operation.chain.extend([link1, link2])

        link3 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link3.used.extend([test_fact1, test_fact2])

        assert not len(planner._get_parent_links((link3)))

        link1.relationships.append(test_rel1)
        assert len(planner._get_parent_links((link3))) == 1
        assert link1 in planner._get_parent_links((link3))

        link2.relationships.append(test_rel2)
        assert len(planner._get_parent_links((link3))) == 2
        assert link1 in planner._get_parent_links((link3))
        assert link2 in planner._get_parent_links((link3))

    def test_links_with_fact_as_relationship(self, setup_planner_test, planning_svc):
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        test_rel1 = Relationship(source=test_fact1)
        test_rel2 = Relationship(source=test_fact1, edge='test_edge', target=test_fact2)
        link1 = Link(command=ability.test, paw=agent.paw, ability=ability)
        link2 = Link(command=ability.test, paw=agent.paw, ability=ability)
        operation.chain.extend([link1, link2])

        assert not len(planner._links_with_fact_as_relationship(test_fact1))
        assert not len(planner._links_with_fact_as_relationship(test_fact2))

        link1.relationships.append(test_rel1)
        assert len(planner._links_with_fact_as_relationship(test_fact1)) is 1
        assert not len(planner._links_with_fact_as_relationship(test_fact2))

        link2.relationships.append(test_rel2)
        assert len(planner._links_with_fact_as_relationship(test_fact1)) is 2
        assert len(planner._links_with_fact_as_relationship(test_fact2)) is 1

    def test_fact_in_relationship(self, setup_planner_test, planning_svc):
        abilities, agent, operation = setup_planner_test
        ability = abilities['detection'][0]
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        test_fact1 = Fact(trait='test_trait1', value='test_value1')
        test_fact2 = Fact(trait='test_trait2', value='test_value2')
        test_rel1 = Relationship(source=test_fact1)
        test_rel2 = Relationship(source=test_fact1, edge='test_edge', target=test_fact2)
        assert planner._fact_in_relationship(test_fact1, test_rel1)
        assert not planner._fact_in_relationship(test_fact2, test_rel1)
        assert planner._fact_in_relationship(test_fact2, test_rel2)
