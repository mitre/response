import pytest
import random
import string

from app.objects.c_ability import Ability
from app.objects.c_adversary import Adversary
from app.objects.c_agent import Agent
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
                                 test=BaseWorld.encode_string(tactic+str(i)), buckets=[tactic], repeatable=True))
        atomic_ordering.append(tactic+str(i))
    return abilities, atomic_ordering


def create_and_store_ability(test_loop, data_service, op, tactic, command, ability_id=None, **kwargs):
    if not ability_id:
        ability_id = ''.join(random.choice(string.ascii_letters) for i in range(5))
    ability = Ability(ability_id=ability_id, tactic=tactic, buckets=[tactic], executor='sh', platform='linux',
                      test=BaseWorld.encode_string(command), **kwargs)
    test_loop.run_until_complete(data_service.store(ability))
    op.adversary.atomic_ordering.append(ability.ability_id)
    return ability


@pytest.fixture
def setup_planner_test(loop, data_svc, init_base_world):
    tagent = Agent(sleep_min=1, sleep_max=2, watchdog=0, executors=['sh'], platform='linux')
    tsource = Source(id='123', name='test', facts=[], adjustments=[])
    toperation = Operation(name='test1', agents=[tagent], adversary=Adversary(name='test', description='test',
                                                                              atomic_ordering=[],
                                                                              adversary_id='XYZ'),
                           source=tsource)

    loop.run_until_complete(data_svc.store(
        Obfuscator(name='plain-text',
                   description='Does no obfuscation to any command, instead running it in plain text',
                   module='plugins.stockpile.app.obfuscators.plain_text')
    ))

    yield tagent, toperation


class TestResponsePlanner:

    @pytest.mark.skip
    async def setup_mock_execute_links(self, planner, operation, link_ids, condition_stop):
        return

    def test_do_detection(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
        mocker.patch.object(planning_svc, 'execute_links', new=self.setup_mock_execute_links)
        agent, operation = setup_planner_test
        abilities = []
        for i in range(3):
            abilities.append(create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation,
                                                      tactic='detection', command='detection'+str(i),
                                                      ability_id='detection'+str(i), repeatable=True))
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)

        loop.run_until_complete(planner.detection())
        assert len(operation.chain) == 3

        loop.run_until_complete(planner.detection())
        assert len(operation.chain) == 6

    def test_do_hunt_no_requirements(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
        """
        This one needs to test the ability to look for unaddressed parent links, and mark these parents as addressed.
        """
        mocker.patch.object(planning_svc, 'execute_links', new=self.setup_mock_execute_links)
        agent, operation = setup_planner_test
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)
        fact1 = Fact(trait='some.test.fact1', value='fact1')
        fact2 = Fact(trait='some.test.fact2', value='fact2')
        rel1 = Relationship(source=fact1, edge='edge', target=fact2)

        link1 = Link(command=tability.test, paw=agent.paw, ability=tability)
        link1.facts.append(fact1)
        link1.facts.append(fact2)
        link1.relationships.append(rel1)
        operation.chain.append(link1)

        hunt1 = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='hunt',
                                         command='#{some.test.fact1}', ability_id='hunt1', repeatable=True)
        hunt2 = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='hunt',
                                         command='#{some.test.fact1} #{some.test.fact2}', ability_id='hunt2',
                                         repeatable=True)

        loop.run_until_complete(planner.hunt())
        assert len(operation.chain) == 3
        assert hunt1.ability_id in [link.ability.ability_id for link in operation.chain]
        assert hunt2.ability_id in [link.ability.ability_id for link in operation.chain]
        assert operation.chain[0] in planner.links_hunted

        link2 = Link(command=tability.test, paw=agent.paw, ability=tability)
        rel2 = Relationship(source=fact2)
        link2.relationships.append(rel2)
        operation.chain.append(link2)

        loop.run_until_complete(planner.hunt())
        assert len(operation.chain) == 5
        assert len([link.ability.ability_id for link in operation.chain if
                    link.ability.ability_id == hunt2.ability_id]) == 2
        assert operation.chain[3] in planner.links_hunted

        link1_clone = Link(command=tability.test, paw=agent.paw, ability=tability)
        link1_clone.relationships.append(rel1)
        operation.chain.append(link1_clone)
        link2_clone = Link(command=tability.test, paw=agent.paw, ability=tability)
        link2_clone.relationships.append(rel2)
        operation.chain.append(link2_clone)

        loop.run_until_complete(planner.hunt())
        assert len(operation.chain) == 9
        assert len([link.ability.ability_id for link in operation.chain if
                    link.ability.ability_id == hunt1.ability_id]) == 2
        assert len([link.ability.ability_id for link in operation.chain if
                    link.ability.ability_id == hunt2.ability_id]) == 3
        assert operation.chain[5] in planner.links_hunted
        assert operation.chain[6] in planner.links_hunted
