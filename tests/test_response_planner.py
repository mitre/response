import copy
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


async def setup_mock_execute_links(planner, operation, link_ids, condition_stop):
    return


@pytest.fixture(scope="function")
def setup_planner_test(loop, mocker, data_svc, init_base_world, planning_svc):
    mocker.patch.object(planning_svc, 'execute_links', new=setup_mock_execute_links)
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

    planner_obj = Planner('test', 'response', 'plugins.response.app.response_planner', dict())
    toperation.planner = planner_obj
    response_planner = ResponsePlanner(operation=toperation, planning_svc=planning_svc)
    response_planner.operation = toperation

    det_ability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=toperation, tactic='detection',
                                           command='detection0', ability_id='detection0', repeatable=True)
    det_link = Link(command=det_ability.test, paw=tagent.paw, ability=det_ability)
    det_link.facts.append(Fact(trait='some.test.fact1', value='fact1', collected_by=tagent.paw))
    det_link.relationships.append(Relationship(source=det_link.facts[0]))
    toperation.chain.append(det_link)

    yield tagent, toperation, planner_obj, response_planner, det_link
    data_svc.ram = copy.deepcopy(data_svc.schema)


class TestResponsePlanner:
    """
    Requires pytest-mock to be installed, and __init__.py files in the plugins directory.
    """

    def test_do_setup(self, loop, data_svc, setup_planner_test, planning_svc):
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic='setup',
                                 command='setup0', ability_id='setup0', repeatable=True)

        loop.run_until_complete(response_planner.setup())
        assert len(operation.chain) == 2
        assert len(response_planner.severity) == 1
        assert response_planner.severity[agent.paw] == 0

        loop.run_until_complete(response_planner.setup())
        assert len(operation.chain) == 2
        assert len(response_planner.severity) == 1

        operation.agents.append(Agent(sleep_min=1, sleep_max=2, watchdog=0, executors=['sh'], platform='linux'))
        loop.run_until_complete(response_planner.setup())
        assert len(operation.chain) == 3
        assert len(response_planner.severity) == 2

    def test_do_detection(self, loop, data_svc, setup_planner_test, planning_svc):
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        abilities = []
        for i in [1, 2]:
            abilities.append(create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation,
                                                      tactic='detection', command='detection'+str(i),
                                                      ability_id='detection'+str(i), repeatable=True))
        planner = ResponsePlanner(operation=operation, planning_svc=planning_svc)

        loop.run_until_complete(planner.detection())
        assert len(operation.chain) == 4

        loop.run_until_complete(planner.detection())
        assert len(operation.chain) == 7

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_1(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        Baseline test - There is a completed link in the operation chain, but it is not a parent. No new links should
        be applied.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test

        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact2}', ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 1
        assert operation.chain[0] == det_link
        assert not len(response_planner._get_link_storage(tactic))

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_2(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There is a completed link in the operation chain that produced a fact that the test_ability uses. One link
        should be applied. The completed link should be added to the set of processed links.
        Rerunning the function should not add any further links.
        Adding a new completed link to the operation that also produced the same fact should cause a new link to be
        applied again. The completed link should be added to the set of processed links.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test

        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact1}', ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 2
        assert operation.chain[1].ability.ability_id == tactic + '1'
        assert len(response_planner._get_link_storage(tactic)) == 1

        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 2
        assert len(response_planner._get_link_storage(tactic)) == 1

        det_link2 = Link(command=det_link.ability.test, paw=agent.paw, ability=det_link.ability)
        det_link2.relationships.append(det_link.relationships[0])
        operation.chain.append(det_link2)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 4
        assert operation.chain[3].ability.ability_id == tactic + '1'
        assert len(response_planner._get_link_storage(tactic)) == 2

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_3(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There is a completed link in the operation chain that produced one fact. This link is placed into the set of
        processed links.
        There is a second completed link in the operation chain that USED (instead of produced) the previously produced
        fact.
        The test ability uses this fact. No link should be applied.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        response_planner._get_link_storage(tactic).add(det_link)

        det_link2 = Link(command=det_link.ability.test, paw=agent.paw, ability=det_link.ability)
        det_link2.used.append(det_link.facts[0])
        det_link2.facts.append(Fact(trait='some.test.fact2', value='fact2', collected_by=agent.paw))
        det_link2.relationships.append(Relationship(source=det_link.facts[0], edge='edge', target=det_link2.facts[0]))
        operation.chain.append(det_link2)

        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact1}', ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 2
        assert operation.chain[0] == det_link
        assert operation.chain[1] == det_link2
        assert len(response_planner._get_link_storage(tactic)) == 1

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_4(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There are two completed links in the operation chain, both of which produced the same fact.
        One link should be applied.
        Both completed links should be added to the set of processed links.
        Repeating the function should cause no further changes.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test

        det_link2 = Link(command=det_link.ability.test, paw=agent.paw, ability=det_link.ability)
        det_link2.relationships.append(det_link.relationships[0])
        operation.chain.append(det_link2)

        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact1}', ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 3
        assert operation.chain[2].ability.ability_id == tactic + '1'
        assert len(response_planner._get_link_storage(tactic)) == 2

        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 3
        assert len(response_planner._get_link_storage(tactic)) == 2

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_5(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There are two completed links in the operation chain. Each link produces a fact of the same trait but with a
        different value.
        Two links should be applied.
        Both completed links should be added to the set of processed links.
        Repeating the function should cause no further changes.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test

        det_link2 = Link(command=det_link.ability.test, paw=agent.paw, ability=det_link.ability)
        det_link2.facts.append(Fact(trait='some.test.fact1', value='fact2', collected_by=agent.paw))
        det_link2.relationships.append(Relationship(source=det_link2.facts[0]))
        operation.chain.append(det_link2)

        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact1}', ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 4
        assert operation.chain[2].ability.ability_id == tactic + '1'
        assert operation.chain[3].ability.ability_id == tactic + '1'
        assert len(response_planner._get_link_storage(tactic)) == 2

        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 4
        assert len(response_planner._get_link_storage(tactic)) == 2

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_6(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There is a completed link in the operation chain that produced a fact that the test_ability uses.
        This link is added to the set of processed links.
        A second completed link in the operation chain produces the same fact, but with a different paw.
        The test ability has a paw provenance requirement for its used fact.
        No links should be applied.
        The second completed link's produced fact's paw is changed to meet the paw provenance requirement.
        A link should be applied.
        The second completed link should be added to the set of processed links.
        Rerunning the function should not add any further links.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        response_planner._get_link_storage(tactic).add(det_link)

        det_link2 = Link(command=det_link.ability.test, paw=agent.paw, ability=det_link.ability)
        det_link2.facts.append(Fact(trait='some.test.fact1', value='fact1', collected_by=agent.paw))
        det_link2.relationships.append(Relationship(source=det_link2.facts[0]))
        operation.chain.append(det_link2)

        det_link2.facts[0].collected_by = 'someotherpaw'

        requirements = [Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                    relationship_match=[dict(source='some.test.fact1')])]
        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact1}', ability_id=tactic + '1', repeatable=True,
                                 requirements=requirements)

        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 2
        assert operation.chain[0] == det_link
        assert operation.chain[1] == det_link2
        assert len(response_planner._get_link_storage(tactic)) == 1

        det_link2.facts[0].collected_by = agent.paw
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 3
        assert operation.chain[2].ability.ability_id == tactic + '1'
        assert len(response_planner._get_link_storage(tactic)) == 2

        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 3
        assert len(response_planner._get_link_storage(tactic)) == 2

    @pytest.mark.parametrize('tactic', ['hunt', 'response'])
    def test_reactive_bucket_7(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There is a completed link in the operation chain that produced one fact. This link is placed into the set of
        processed links.
        There is a second completed link which USES the previously produced fact, produces a new fact, and a
        relationship. This relationship satisfies the multi-fact requirement of the test ability.
        A link should be applied.
        The second completed link should be added to the set of processed links.
        Calling the function again should not result in any changes.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        response_planner._get_link_storage(tactic).add(det_link)

        det_link2 = Link(command=det_link.ability.test, paw=agent.paw, ability=det_link.ability)
        det_link2.used.append(det_link.facts[0])
        det_link2.facts.append(Fact(trait='some.test.fact2', value='fact2', collected_by=agent.paw))
        det_link2.relationships.append(Relationship(source=det_link.facts[0], edge='edge', target=det_link2.facts[0]))
        operation.chain.append(det_link2)

        test_ability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                                command='#{some.test.fact1} #{some.test.fact2}',
                                                ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 3
        assert operation.chain[2].ability.ability_id == test_ability.ability_id
        assert len(response_planner._get_link_storage(tactic)) == 2

    def test_response_paw_prov(self, loop, data_svc, planning_svc, setup_planner_test):
        """
        There is a completed link run by a (non-existent) agent that produces a fact.
        The test ability uses this fact on a different (existing) agent, without a paw provenance requirement.
        No link should be applied, because response should assure parent links were run on the same agent.
        """
        tactic = 'response'
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        det_link.facts[0].collected_by = 'someotherpaw'

        create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation, tactic=tactic,
                                 command='#{some.test.fact1} #{some.test.fact2}',
                                 ability_id=tactic + '1', repeatable=True)
        loop.run_until_complete(getattr(response_planner, tactic)())
        assert len(operation.chain) == 1
        assert operation.chain[0] == det_link
        assert not len(response_planner._get_link_storage(tactic))

    def test_severity_modifier1(self, loop, data_svc, planning_svc, setup_planner_test):
        """
        There is one completed link with a produced detection and a severity modifier.
        Running execute should cause the severity score to be modified appropriately.
        Running execute again should not change anything.
        Two new completed links are added - one with the same paw as the first, and one with a different paw.
        Running execute should cause the two severity scores to be modified appropriately.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        det_link.ability.additional_info['severity_modifier'] = 5
        response_planner.next_bucket = None
        response_planner.severity[agent.paw] = 0

        loop.run_until_complete(response_planner.execute())
        assert len(response_planner.severity) == 1
        assert response_planner.severity[agent.paw] == 5

        loop.run_until_complete(response_planner.execute())
        assert len(response_planner.severity) == 1
        assert response_planner.severity[agent.paw] == 5

        det_link2 = copy.copy(det_link)
        det_link2.command = "a different command"

        det_link_other = Link(command=det_link.ability.test, paw='someotherpaw', ability=det_link.ability)
        det_link_other.facts.append(Fact(trait='some.test.fact2', value='fact2', collected_by='someotherpaw'))
        det_link_other.relationships.append(Relationship(source=det_link.facts[0],
                                                         edge='edge',
                                                         target=det_link_other.facts[0]))
        response_planner.severity[det_link_other.paw] = 0

        operation.chain.extend([det_link2, det_link_other])
        loop.run_until_complete(response_planner.execute())
        assert len(response_planner.severity) == 2
        assert response_planner.severity[agent.paw] == 10
        assert response_planner.severity['someotherpaw'] == 5

    def test_severity_modifier2(self, loop, data_svc, planning_svc, setup_planner_test):
        """
        A completed link that produced no detections should result in no changes to the severity score.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        det_link.ability.additional_info['severity_modifier'] = 5
        det_link.facts = []
        det_link.relationships = []
        response_planner.next_bucket = None
        response_planner.severity[agent.paw] = 0

        loop.run_until_complete(response_planner.execute())
        assert len(response_planner.severity) == 1
        assert response_planner.severity[agent.paw] == 0

    def test_severity_modifier3(self, loop, data_svc, planning_svc, setup_planner_test):
        """
        A new detection with the same command, paw, and relationships as a previous, unresponded detection should not
        affect the severity score.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        det_link.ability.additional_info['severity_modifier'] = 5
        response_planner.next_bucket = None
        response_planner.severity[agent.paw] = 0

        loop.run_until_complete(response_planner.execute())
        assert len(response_planner.severity) == 1
        assert response_planner.severity[agent.paw] == 5

        det_link_copy = copy.copy(det_link)

        operation.chain.append(det_link_copy)
        loop.run_until_complete(response_planner.execute())
        assert len(response_planner.severity) == 1
        assert response_planner.severity[agent.paw] == 5

    def test_severity_requirement(self, loop, data_svc, planning_svc, setup_planner_test):
        """
        A response ability whose severity requirement is not met should not be applied to the operation.
        When the severity score is adjusted appropriately and this is attempted again, the ability should be applied.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        response_planner.severity[agent.paw] = 0
        response_ability = create_and_store_ability(test_loop=loop, data_service=data_svc, op=operation,
                                                    tactic='response', command='response', ability_id='response1',
                                                    repeatable=True)
        response_ability.additional_info['severity_requirement'] = 50
        loop.run_until_complete(response_planner.response())
        assert len(operation.chain) == 1

        response_planner.severity[agent.paw] = 50
        response_ability.additional_info['severity_requirement'] = 50
        loop.run_until_complete(response_planner.response())
        assert len(operation.chain) == 2

    @pytest.mark.parametrize('tactic', ['detection', 'hunt'])
    def test_is_detection_not_responded_to(self, loop, data_svc, planning_svc, setup_planner_test, tactic):
        """
        There is a detection that has been processed but not responded to. The function should determine that a new,
        identical detection/hunt ability matches another link with the above condition.
        A match is determined by the links' paws and commands. Therefore, a hunt ability can be compared with a
        detection ability to determine matches.
        Once the original detection has been marked as responded to, the identical detection should be determined to be
        responded to.
        """
        agent, operation, planner_obj, response_planner, det_link = setup_planner_test
        response_planner.next_bucket = None
        response_planner.severity[agent.paw] = 0
        loop.run_until_complete(response_planner.execute())

        copy_ability = copy.copy(det_link.ability)
        copy_ability.tactic = tactic
        copy_ability.buckets = [tactic]
        identical_det_link = Link(command=copy_ability.test, paw=agent.paw, ability=copy_ability)
        assert loop.run_until_complete(response_planner._is_detection_not_responded_to(identical_det_link))

        response_planner.links_responded.add(det_link)
        assert not loop.run_until_complete(response_planner._is_detection_not_responded_to(identical_det_link))
