from aiohttp_jinja2 import template
from aiohttp import web

from app.utility.base_service import BaseService
from plugins.response.app.response_svc import ResponseService


class ResponseApi(BaseService):

    def __init__(self, services):
        self.data_svc = services.get('data_svc')
        self.resp_svc = ResponseService(services)

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        operations = [a for a in await self.data_svc.locate('operations')]
        return dict(abilities=abilities, adversaries=adversaries, operations=operations)

    async def update(self, request):
        body = await request.json()
        info = body.get('info')
        operation_id = body.get('operation')
        operation = self.data_svc.locate('operations', match={'id': operation_id})
        if info == 'hosts':
            body = self.resp_svc.get_hosts(operation)
        elif info == 'status':
            body = self.resp_svc.update_status(operation)
        return web.Response(body=body)
