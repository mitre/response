import pytest
import yaml

from app.utility.base_world import BaseWorld
from app.service.data_svc import DataService
from app.service.planning_svc import PlanningService


@pytest.fixture(scope='session')
def init_base_world():
    with open('../../../conf/default.yml') as c:
        BaseWorld.apply_config('main', yaml.load(c, Loader=yaml.FullLoader))
    BaseWorld.apply_config('agents', BaseWorld.strip_yml('../../../conf/agents.yml')[0])
    BaseWorld.apply_config('payloads', BaseWorld.strip_yml('../../../conf/payloads.yml')[0])


@pytest.fixture(scope='class')
def data_svc():
    return DataService()


@pytest.fixture(scope='class')
def planning_svc():
    return PlanningService()
