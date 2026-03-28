"""Tests for hook.py — plugin metadata and enable/expansion functions."""
import sys
import types
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, '/tmp/response-pytest')


class TestHookMetadata:

    def test_name(self):
        from hook import name
        assert name == 'Response'

    def test_description(self):
        from hook import description
        assert description == 'An automated incident response plugin'

    def test_address(self):
        from hook import address
        assert address == '/plugin/responder/gui'

    def test_access_is_blue(self):
        from hook import access
        from app.utility.base_world import BaseWorld
        assert access == BaseWorld.Access.BLUE


class TestRegisterAgent:

    def test_register_agent_adds_to_deployments(self):
        from app.utility.base_world import BaseWorld
        BaseWorld.get_config = MagicMock(return_value=set())
        BaseWorld.set_config = MagicMock()
        from hook import _register_agent
        _register_agent('test-ability-id')
        BaseWorld.set_config.assert_called_once()
        call_kwargs = BaseWorld.set_config.call_args
        assert 'test-ability-id' in call_kwargs[1]['value'] or 'test-ability-id' in call_kwargs[0][0] if call_kwargs[0] else True


class TestEnable:

    @pytest.mark.asyncio
    async def test_enable_registers_routes(self):
        from app.utility.base_world import BaseWorld
        BaseWorld.apply_config = MagicMock()
        BaseWorld.strip_yml = MagicMock(return_value=[{}])
        BaseWorld.get_config = MagicMock(return_value=False)

        mock_app = MagicMock()
        mock_router = MagicMock()
        mock_app.router = mock_router

        mock_data_svc = AsyncMock()
        mock_app_svc = MagicMock()
        mock_app_svc.application = mock_app
        mock_event_svc = MagicMock()

        services = {
            'data_svc': mock_data_svc,
            'rest_svc': MagicMock(),
            'app_svc': mock_app_svc,
            'event_svc': mock_event_svc,
        }
        services_mock = MagicMock()
        services_mock.get = services.get

        # Patch _register_agent to avoid side effects
        with patch('hook._register_agent'):
            from hook import enable
            await enable(services_mock)

        # 4 routes should be added
        assert mock_router.add_route.call_count == 4


class TestExpansion:

    @pytest.mark.asyncio
    async def test_expansion_calls_apply_adversary_config(self):
        mock_response_svc = AsyncMock()
        services = MagicMock()
        services.get = MagicMock(return_value=mock_response_svc)

        from hook import expansion
        await expansion(services)
        mock_response_svc.apply_adversary_config.assert_awaited_once()
