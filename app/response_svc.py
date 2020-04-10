from aiohttp_jinja2 import template
import asyncio

from app.utility.base_service import BaseService
from app.utility.event import Observer


class LinkAddedObserver(Observer):

    def __init__(self, rest_svc):
        Observer.__init__(self, 'link', 'added')
        self.rest_svc = rest_svc

    def handle(self):
        access = dict(access=(self.rest_svc.Access.BLUE,))
        data = {
            'name': 'Auto-Collect Blue Data',
            'group': 'blue',
            'adversary_id': 'f61e3fc0-43d8-4b36-b5d3-710610b92974',
            'auto_close': 1,
        }
        loop = asyncio.get_event_loop()
        loop.create_task(self.rest_svc.create_operation(access, data))


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')

        rest_svc = services.get('rest_svc')
        LinkAddedObserver.register(rest_svc)

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        return dict(abilities=abilities, adversaries=adversaries)
