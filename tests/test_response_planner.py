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
from app.objects.c_planner import Planner
from app.objects.secondclass.c_relationship import Relationship
from app.objects.secondclass.c_requirement import Requirement
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

    def test_hunt_no_requirements(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
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

    def test_hunt_with_paw_provenance(self, loop, data_svc, mocker, setup_planner_test, planning_svc):

        assert True

    def test_do_link_relationships_satisfy_requirements_paw_prov(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
        agent, operation = setup_planner_test
        planner = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
        response_planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        operation.planner = planner

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)
        link1 = Link(command=tability.test, paw=agent.paw, ability=tability)
        fact1 = Fact(trait='some.test.fact1', value='fact1', collected_by='someotherpaw')
        rel1 = Relationship(source=fact1)
        link1.facts.append(fact1)
        link1.relationships.append(rel1)
        # operation.chain.append(link1)

        ability_paw_prov = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='test',
                                                    command='#{some.test.fact1}', ability_id='test1', repeatable=True)
        ability_paw_prov.requirements.append(Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                         relationship_match=[dict(source='some.test.fact1')]))

        link_paw_prov = Link(command='#{some.test.fact1}', paw=agent.paw, ability=ability_paw_prov)
        link_paw_prov.used.append(fact1)
        assert not loop.run_until_complete(response_planner._do_link_relationships_satisfy_requirements(link_paw_prov, link1))

        fact1.collected_by = agent.paw
        assert loop.run_until_complete(response_planner._do_link_relationships_satisfy_requirements(link_paw_prov, link1))

    def test_do_link_relationships_satisfy_requirements_basic_req(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
        agent, operation = setup_planner_test
        planner = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
        response_planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        operation.planner = planner

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)
        link1 = Link(command=tability.test, paw=agent.paw, ability=tability)
        fact1 = Fact(trait='some.test.fact1', value='fact1', collected_by=agent.paw)
        fact2 = Fact(trait='some.test.fact2', value='fact2', collected_by=agent.paw)
        rel1 = Relationship(source=fact1, edge='wrong_edge', target=fact2)
        link1.facts.extend([fact1, fact2])
        link1.relationships.append(rel1)

        ability_basic_req = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='test',
                                                     command='#{some.test.fact1} #{some.test.fact2}',
                                                     ability_id='test1', repeatable=True)
        ability_basic_req.requirements.append(Requirement(module='plugins.stockpile.app.requirements.basic',
                                                          relationship_match=[dict(source='some.test.fact1',
                                                                                   edge='right_edge',
                                                                                   target='some.test.fact2')]))
        link_basiq_req = Link(command='#{some.test.fact1} #{some.test.fact2}', paw=agent.paw, ability=ability_basic_req)
        link_basiq_req.used.extend([fact1, fact2])
        assert not loop.run_until_complete(
            response_planner._do_link_relationships_satisfy_requirements(link_basiq_req, link1))

        rel1.edge = 'right_edge'
        assert loop.run_until_complete(response_planner._do_link_relationships_satisfy_requirements(link_basiq_req, link1))

    def test_do_link_relationships_satisfy_requirements_multiple(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
        agent, operation = setup_planner_test
        planner = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
        response_planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        operation.planner = planner

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)
        link1 = Link(command=tability.test, paw=agent.paw, ability=tability)
        fact1 = Fact(trait='some.test.fact1', value='fact1', collected_by='someotherpaw')
        fact2 = Fact(trait='some.test.fact2', value='fact2', collected_by=agent.paw)
        rel1 = Relationship(source=fact1, edge='wrong_edge', target=fact2)
        link1.facts.extend([fact1, fact2])
        link1.relationships.append(rel1)

        ability_mult_req = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='test',
                                                    command='#{some.test.fact1} #{some.test.fact2}', ability_id='test1',
                                                    repeatable=True)
        ability_mult_req.requirements.append(Requirement(module='plugins.stockpile.app.requirements.basic',
                                                         relationship_match=[dict(source='some.test.fact1',
                                                                                  edge='right_edge',
                                                                                  target='some.test.fact2')]))
        ability_mult_req.requirements.append(Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                         relationship_match=[dict(source='some.test.fact1')]))

        link_mult_req = Link(command='#{some.test.fact1} #{some.test.fact2}', paw=agent.paw, ability=ability_mult_req)
        link_mult_req.used.extend([fact1, fact2])
        assert not loop.run_until_complete(
            response_planner._do_link_relationships_satisfy_requirements(link_mult_req, link1))

        rel1.edge = 'right_edge'
        assert loop.run_until_complete(
            response_planner._do_link_relationships_satisfy_requirements(link_mult_req, link1))

        rel1.edge = 'wrong_edge'
        fact1.collected_by = agent.paw
        assert loop.run_until_complete(
            response_planner._do_link_relationships_satisfy_requirements(link_mult_req, link1))

    def test_hunt_with_requirements(self, loop, data_svc, mocker, setup_planner_test, planning_svc):
        """
        This one needs to test the ability to look for unaddressed parent links, and mark these parents as addressed.
        """
        mocker.patch.object(planning_svc, 'execute_links', new=self.setup_mock_execute_links)
        agent, operation = setup_planner_test
        planner = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
        response_planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        operation.planner = planner

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)

        link1 = Link(command=tability.test, paw=agent.paw, ability=tability)
        fact1 = Fact(trait='some.test.fact1', value='fact1', collected_by='someotherpaw')
        fact2 = Fact(trait='some.test.fact2', value='fact2', collected_by=agent.paw)
        rel1 = Relationship(source=fact1, edge='wrong_edge', target=fact2)
        link1.facts.extend([fact1, fact2])
        link1.relationships.append(rel1)
        operation.chain.append(link1)

        ability_mult_req = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='test',
                                                    command='#{some.test.fact1} #{some.test.fact2}', ability_id='test1',
                                                    repeatable=True)
        ability_mult_req.requirements.append(Requirement(module='plugins.stockpile.app.requirements.basic',
                                                         relationship_match=[dict(source='some.test.fact1',
                                                                                  edge='right_edge',
                                                                                  target='some.test.fact2')]))
        ability_mult_req.requirements.append(Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                         relationship_match=[dict(source='some.test.fact1')]))

        # want to add one link with fact1, then test. should fail
        # add another link with fact1

        hunt1 = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='hunt',
                                         command='#{some.test.fact1}', ability_id='hunt1', repeatable=True)
        hunt2 = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='hunt',
                                         command='#{some.test.fact1} #{some.test.fact2}', ability_id='hunt2',
                                         repeatable=True)

        loop.run_until_complete(response_planner.hunt())
        assert len(operation.chain) == 3
        assert hunt1.ability_id in [link.ability.ability_id for link in operation.chain]
        assert hunt2.ability_id in [link.ability.ability_id for link in operation.chain]
        assert operation.chain[0] in response_planner.links_hunted

        link2 = Link(command=tability.test, paw=agent.paw, ability=tability)
        rel2 = Relationship(source=fact2)
        link2.relationships.append(rel2)
        operation.chain.append(link2)

        loop.run_until_complete(response_planner.hunt())
        assert len(operation.chain) == 5
        assert len([link.ability.ability_id for link in operation.chain if
                    link.ability.ability_id == hunt2.ability_id]) == 2
        assert operation.chain[3] in response_planner.links_hunted

        link1_clone = Link(command=tability.test, paw=agent.paw, ability=tability)
        link1_clone.relationships.append(rel1)
        operation.chain.append(link1_clone)
        link2_clone = Link(command=tability.test, paw=agent.paw, ability=tability)
        link2_clone.relationships.append(rel2)
        operation.chain.append(link2_clone)

        loop.run_until_complete(response_planner.hunt())
        assert len(operation.chain) == 9
        assert len([link.ability.ability_id for link in operation.chain if
                    link.ability.ability_id == hunt1.ability_id]) == 2
        assert len([link.ability.ability_id for link in operation.chain if
                    link.ability.ability_id == hunt2.ability_id]) == 3
        assert operation.chain[5] in response_planner.links_hunted
        assert operation.chain[6] in response_planner.links_hunted

    def test_create_test_op_and_links(self, loop, data_svc, setup_planner_test, planning_svc):
        # With a link with a basic requirement and a paw prov requirement, and a potential parent link with the relevant
        # facts in it its relationships, I want to see that these facts are given to the potential parent copy and that
        # the correct number of test links are created
        agent, operation = setup_planner_test
        planner = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
        response_planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        operation.planner = planner

        fact1 = Fact(trait='some.test.fact1', value='fact1', collected_by='someotherpaw')
        fact2 = Fact(trait='some.test.fact2', value='fact2', collected_by='someotherpaw')
        fact3 = Fact(trait='some.test.fact3', value='fact3', collected_by='someotherpaw')
        rel1 = Relationship(source=fact1, edge='edge', target=fact2)
        rel2 = Relationship(source=fact3)

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)

        potential_parent_link = Link(command=tability.test, paw=agent.paw, ability=tability)
        potential_parent_link.relationships.extend([rel1, rel2])
        potential_parent_link.used.append(fact1)

        test_ability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='hunt',
                                                command='#{some.test.fact1} #{some.test.fact2} #{some.test.fact3}',
                                                ability_id='hunt1', repeatable=True)
        test_ability.requirements.append(Requirement(module='plugins.stockpile.app.requirements.basic',
                                         relationship_match=[dict(source='some.test.fact1', edge='right_edge',
                                                                  target='some.test.fact2')]))
        test_ability.requirements.append(Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                     relationship_match=[dict(source='some.test.fact1')]))
        test_link = Link(command=test_ability.test, paw=agent.paw, ability=test_ability)
        links, test_op = response_planner._create_test_op_and_links(test_link, potential_parent_link,
                                                                    test_ability.requirements)
        assert len(test_op.chain) == 1
        assert len(test_op.chain[0].facts) == 2
        assert all(f in [fact.trait for fact in test_op.chain[0].facts] for f in ['some.test.fact2', 'some.test.fact3'])
        paws = set([fact.collected_by for fact in test_op.chain[0].facts])
        assert len(paws) == 1
        assert agent.paw in paws
        assert len(links) == 2
        assert all(len(link.ability.requirements) == 1 for link in links)

    def test_do_link_relationships_satisfy_requirements(self, loop, data_svc, setup_planner_test, planning_svc):
        agent, operation = setup_planner_test
        planner = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
        response_planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)
        operation.planner = planner

        fact1 = Fact(trait='some.test.fact1', value='fact1', collected_by=agent.paw)
        fact2 = Fact(trait='some.test.fact2', value='fact2', collected_by=agent.paw)
        fact3 = Fact(trait='some.test.fact3', value='fact3', collected_by=agent.paw)
        rel1 = Relationship(source=fact1, edge='edge', target=fact2)
        rel2 = Relationship(source=fact3)

        tability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='detection',
                                            command='detection0', ability_id='detection0', repeatable=True)

        potential_parent_link = Link(command=tability.test, paw=agent.paw, ability=tability)
        potential_parent_link.relationships.extend([rel1, rel2])
        potential_parent_link.used.append(fact1)

        test_ability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='hunt',
                                                command='#{some.test.fact1} #{some.test.fact2} #{some.test.fact3}',
                                                ability_id='hunt1', repeatable=True)
        test_ability.requirements.append(Requirement(module='plugins.stockpile.app.requirements.basic',
                                                     relationship_match=[
                                                         dict(source='some.test.fact1', edge='edge',
                                                              target='some.test.fact2')]))
        test_ability.requirements.append(Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                     relationship_match=[dict(source='some.test.fact1')]))
        test_link = Link(command=test_ability.test, paw=agent.paw, ability=test_ability)
        test_link.used.extend([fact1, fact2, fact3])

        assert loop.run_until_complete(response_planner._do_link_relationships_satisfy_requirements(test_link, potential_parent_link)) == 2

