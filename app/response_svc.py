from aiohttp_jinja2 import template

from app.utility.base_service import BaseService


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.file_svc = services.get('file_svc')
        self.app_svc = services.get('app_svc')
        self.data_svc = services.get('data_svc')

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        return dict(abilities=abilities, adversaries=adversaries)
