from app.utility.base_world import BaseWorld
from plugins.response.app.response_svc import ResponseService

name = 'Response'
description = 'An automated incident response plugin'
address = '/plugin/responder/gui'
access = BaseWorld.Access.BLUE


async def enable(services):
    BaseWorld.apply_config('response', BaseWorld.strip_yml('plugins/response/conf/response.yml')[0])
    response_svc = ResponseService(services)
    app = services.get('app_svc').application
    app.router.add_route('GET', '/plugin/responder/gui', response_svc.splash)
    app.router.add_route('POST', '/plugin/responder/update', response_svc.update_responder)

    await response_svc.register_handler(services.get('event_svc'))
