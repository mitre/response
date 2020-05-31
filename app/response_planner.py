import copy

from app.objects.secondclass.c_fact import Fact
from app.objects.c_operation import Operation
from app.objects.secondclass.c_requirement import Requirement


class LogicalPlanner:

    def __init__(self, operation, planning_svc, stopping_conditions=()):
        self.operation = operation
        self.planning_svc = planning_svc
        self.stopping_conditions = stopping_conditions
        self.stopping_condition_met = False
        self.state_machine = ['detection', 'hunt', 'response']
        self.next_bucket = 'detection'
        self.links_hunted = set()
        self.links_responded = set()
        self.severity = dict()

    async def execute(self):
        await self.planning_svc.execute_planner(self)

    async def detection(self):
        await self.planning_svc.exhaust_bucket(self, ['detection'], self.operation, batch=True)
        self.next_bucket = await self.planning_svc.default_next_bucket('detection', self.state_machine)

    async def hunt(self):
        await self._do_reactive_bucket(bucket='hunt')
        self.next_bucket = await self.planning_svc.default_next_bucket('hunt', self.state_machine)

    async def response(self):
        await self._do_reactive_bucket(bucket='response')
        self.next_bucket = await self.planning_svc.default_next_bucket('response', self.state_machine)

    """ PRIVATE """

    async def _do_reactive_bucket(self, bucket):
        link_storage = self._get_link_storage(bucket)
        links = await self.planning_svc.get_links(planner=self, operation=self.operation, buckets=[bucket])
        print(links)
        links_to_apply = []
        links_being_addressed = set()
        for link in links:
            if link.used:
                check_paw_prov = True if bucket in ['response'] else False
                unaddressed_parents = self._get_unaddressed_parent_links(link, link_storage, check_paw_prov)
                if len(unaddressed_parents):
                    links_to_apply.append(link)
                    links_being_addressed.update(unaddressed_parents)
            else:
                links_to_apply.append(link)
        link_storage.update(list(links_being_addressed))
        await self._run_links(links_to_apply)

    def _get_link_storage(self, bucket):
        storage = dict(
            hunt=self.links_hunted,
            response=self.links_responded
        )
        return storage[bucket]

    def _get_unaddressed_parent_links(self, link, link_storage, check_paw_prov=False):
        unaddressed_links = [unaddressed for unaddressed in self._get_parent_links(link, check_paw_prov) if
                             unaddressed not in link_storage]
        unaddressed_parents = []
        for ul in unaddressed_links:
            if self._do_link_relationships_satisfy_requirements(link, ul):
                unaddressed_parents.append(ul)
        return unaddressed_parents

    def _get_parent_links(self, link, check_paw_prov=False):
        parent_links = set()
        link_paw = link.paw if check_paw_prov else None
        for fact in link.used:
            parent_links.update(self._links_with_fact_in_relationship(fact, link_paw))
        return parent_links

    def _links_with_fact_in_relationship(self, fact, paw=None):
        links_with_fact = []
        for link in self.operation.chain if paw is None else [lnk for lnk in self.operation.chain if lnk.paw == paw]:
            if any(self._fact_in_relationship(fact, rel) for rel in link.relationships):
                links_with_fact.append(link)
        return links_with_fact

    @staticmethod
    def _fact_in_relationship(fact, relationship):
        for f in [relationship.source, relationship.target]:
            if f and f.trait == fact.trait and f.value == fact.value:
                return True
        return False

    async def _do_link_relationships_satisfy_requirements(self, link, potential_parent):
        # Need to add case where if no relevant_requirement for used fact, then return True
        # Consider changing relevant_requirements to dict of requirement_unique -> (req, [fact(s)])
        used_facts = [fact for fact in link.used for rel in potential_parent.relationships if
                      self._fact_in_relationship(fact, rel)]
        relevant_requirements_and_facts = dict()
        for fact in used_facts:
            rel_reqs_for_fact = self._get_relevant_requirements_for_fact_in_link(link, fact)
            if not rel_reqs_for_fact:
                return 1
            for rel_req in rel_reqs_for_fact:
                req_unique = self._unique_for_requirement(rel_req)
                if req_unique in relevant_requirements_and_facts:
                    relevant_requirements_and_facts[req_unique]['facts'].append(fact)
                else:
                    relevant_requirements_and_facts[req_unique] = dict(requirement=rel_req, facts=[fact])
        links_with_relevant_reqs, verifier_operation = self._create_test_op_and_links(link, potential_parent,
                                                                                      relevant_requirements_and_facts)
        return len(await self.planning_svc.remove_links_missing_requirements(links_with_relevant_reqs,
                                                                             verifier_operation)) if \
            relevant_requirements_and_facts else 0

    @staticmethod
    def _get_relevant_requirements_for_fact_in_link(link, fact):
        relevant_requirements = []
        for req in link.ability.requirements:
            for req_match in req.relationship_match:
                if fact.trait == req_match['source'] or 'target' in req_match and fact.trait == req_match['target']:
                    relevant_requirements.append(Requirement(module=req.module, relationship_match=[req_match]))
        return relevant_requirements

    @staticmethod
    def _unique_for_requirement(requirement):
        rel_match = requirement.relationship_match[0]
        unique = requirement.module + rel_match['source']
        for field in ['edge', 'target']:
            if field in rel_match:
                unique += rel_match[field]
        return unique

    def _create_test_op_and_links(self, link, potential_parent, relevant_requirements_and_facts):
        """
        This function creates a test operation and test links. The test operation contains a copy of the potential
        parent. This copy link is given all the facts that it produced, determined by
        set(facts_in_relationships) - set(used_facts).
        The test links are copies of the link to be applied. Each of these is given one relevant requirement to
        be tested for.
        Relevant requirements are provided by the calling function, but then filtered to ensure that each requirement
        uses at least one fact produced by the parent.
        """
        verifier_operation = Operation(name='verifier', agents=[], adversary=None, planner=self.operation.planner)
        potential_parent_copy = copy.copy(potential_parent)
        produced_facts = [fact for fact in self._facts_from_link_relationships(potential_parent) if
                          not self._is_fact_used(fact, potential_parent)]
        replacement_produced_facts = [Fact(trait=fact.trait, value=fact.value, collected_by=potential_parent.paw) for
                                      fact in produced_facts]
        potential_parent_copy.facts = replacement_produced_facts
        verifier_operation.chain.append(potential_parent_copy)
        filtered_rel_reqs_and_facts = self._filter_reqs_by_used_facts(relevant_requirements_and_facts, produced_facts)
        links_with_relevant_reqs_and_facts = self._create_test_links(link, filtered_rel_reqs_and_facts)
        return links_with_relevant_reqs_and_facts, verifier_operation

    @staticmethod
    def _facts_from_link_relationships(link):
        relationship_facts = []
        for rel in link.relationships:
            relationship_facts.extend([rel.source, rel.target] if rel.target else [rel.source])
        return relationship_facts

    @staticmethod
    def _is_fact_used(fact, link):
        for used in link.used:
            if fact.trait == used.trait and fact.value == used.value:
                return True
        return False

    def _filter_reqs_by_used_facts(self, requirements_and_facts, filter_facts):
        filtered_reqs_and_facts = dict()
        for req in requirements_and_facts:
            if any(self._do_facts_match(req_fact, filter_f) for
                   req_fact in requirements_and_facts[req]['facts'] for filter_f in filter_facts):
                filtered_reqs_and_facts[req] = requirements_and_facts[req]
        return filtered_reqs_and_facts

    @staticmethod
    def _do_facts_match(fact1, fact2):
        return fact1.trait == fact2.trait and fact1.value == fact2.value

    @staticmethod
    def _create_test_links(original_link, requirements_and_facts):
        links = []
        for req in requirements_and_facts:
            link_with_req = copy.copy(original_link)
            ability_with_req = copy.copy(original_link.ability)
            ability_with_req.requirements = [requirements_and_facts[req]['requirement']]
            link_with_req.ability = ability_with_req
            link_with_req.facts = requirements_and_facts[req]['facts']
            links.append(link_with_req)
        return links

    async def _run_links(self, links):
        link_ids = []
        for link in links:
            link_ids.append(await self.operation.apply(link))
        await self.planning_svc.execute_links(self, self.operation, link_ids, True)



####### If response, want to make sure "parent" links are from the same agent - check paw provenance
####### If fact is in link's relationship, but not in link's facts, check if the fact is in link's used list. If not, add it to link's facts to satisfy paw prov requirements.


    # async def execute(self, **kwargs):
    #     links = await self.planning_svc.get_links(operation=self.operation,
    #                                               stopping_conditions=self.stopping_conditions, planner=self)
    #     to_apply, detections_being_handled = self.select_links(links)
    #     for link in to_apply:
    #         await self.operation.apply(link)
    #     self.handled_detection_and_response_links.extend(list(detections_being_handled))
    #
    # def select_links(self, links):
    #     to_apply = []
    #     detections_being_handled = set()
    #     for link in links:
    #         if link.ability.tactic == 'detection':
    #             to_apply.append(link)
    #         elif any(uf not in self.handled_detection_and_response_links for uf in link.used) and \
    #                 link.ability.tactic in ['hunt', 'response']:
    #             to_apply.append(link)
    #             if link.ability.tactic == 'response':
    #                 detections_being_handled.update(link.used)
    #     return to_apply, detections_being_handled
