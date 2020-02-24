from app.utility.base_world import BaseWorld
from plugins.response.app.response_api import ResponseApi

name = 'Response'
description = 'An automated incident response plugin'
address = '/plugin/responder/gui'
access = BaseWorld.Access.BLUE


async def enable(services):
    response_api = ResponseApi(services)
    app = services.get('app_svc').application
    app.router.add_route('GET', '/plugin/responder/gui', response_api.splash)
    app.router.add_route('POST', '/plugin/responder/update', response_api.update)
