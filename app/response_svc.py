from aiohttp_jinja2 import template
import asyncio
import uuid

from app.utility.base_service import BaseService
from app.utility.event import Observer


class LinkCompletedObserver(Observer):

    def __init__(self, rest_svc):
        Observer.__init__(self, 'link', 'completed')
        self.rest_svc = rest_svc

    async def handle(self, agent, pid):
        if agent.group == 'blue':
            return

        access = dict(access=(self.rest_svc.Access.BLUE,))

        source_id = str(uuid.uuid4())
        source_name = 'blue-pid-{}'.format(source_id),
        source_data = dict(
            id=source_id,
            name=source_name,
            facts=[dict(trait='host.process.id', value=pid)],
        )
        op_data = dict(
            name='Auto-Collect Blue Data',
            group='blue',
            adversary_id='f61e3fc0-43d8-4b36-b5d3-710610b92974',
            source=source_name,
            auto_close=0,
        )
        loop = asyncio.get_event_loop()
        await loop.create_task(self.rest_svc.persist_source(source_data))
        loop.create_task(self.rest_svc.create_operation(access, op_data))


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')

        rest_svc = services.get('rest_svc')
        LinkCompletedObserver.register(rest_svc)

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        return dict(abilities=abilities, adversaries=adversaries)
