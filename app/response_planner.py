class LogicalPlanner:

    def __init__(self, operation, planning_svc, stopping_conditions=()):
        self.operation = operation
        self.planning_svc = planning_svc
        self.stopping_conditions = stopping_conditions
        self.stopping_condition_met = False
        self.processed_links = []
        self.handled_detections = []    #stores completed links that are processed
        self.severity = 0

    async def execute(self, phase):
        self.process_completed_links()
        detections_being_handled = []
        for link in await self.planning_svc.get_links(operation=self.operation, phase=phase,
                                                      stopping_conditions=self.stopping_conditions, planner=self):
            if link.ability.tactic == 'detection':
                await self.operation.apply(link)
            elif link.ability.tactic == 'hunt':
                if any(uf not in self.handled_detections for uf in link.used):
                    await self.operation.apply(link)
            elif link.ability.tactic == 'response':
                if any(uf not in self.handled_detections for uf in link.used) and link.visibility.score() > self.severity:
                    await self.operation.apply(link)
                    detections_being_handled.append(uf for uf in link.used if uf not in self.detections_to_handle)
            await self.operation.apply(link)
        self.handled_detections.extend(detections_being_handled)

    def process_completed_links(self):
        for l in [link for link in self.operation.chain if link not in self.processed_links]:
            for rel in l.relationships:
                if rel.trait == 'operation.severity.modifier' and l.relationships.length() > 1:
                    self.severity += rel.edge
            self.processed_links.append(l)