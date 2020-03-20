class LogicalPlanner:

    def __init__(self, operation, planning_svc, stopping_conditions=()):
        self.operation = operation
        self.planning_svc = planning_svc
        self.stopping_conditions = stopping_conditions
        self.stopping_condition_met = False
        self.handled_detections = []
        self.severity = 0

    async def execute(self, phase):
        for link in await self.planning_svc.get_links(operation=self.operation, phase=phase,
                                                      stopping_conditions=self.stopping_conditions, planner=self):
            if link.ability.tactic == 'detection':
                await self.operation.apply(link)
            elif link.ability.tactic == 'hunt':
                if any(uf not in self.handled_detections for uf in link.used):
                    await self.operation.apply(link)
            await self.operation.apply(link)
