import pytest
from inference_gateway import FakeBackend, InferenceGateway, InferenceRequest, CircuitState

@pytest.mark.asyncio
async def test_gateway_primary_success():
    primary = FakeBackend(name="primary", default_response="Primary response")
    fallback = FakeBackend(name="fallback", default_response="Fallback response")
    gateway = InferenceGateway(primary=primary, fallback=fallback)

    req = InferenceRequest(messages=[{"role": "user", "content": "hello"}])
    res = await gateway.generate(req)
    assert res.content == "Primary response"
    assert res.backend_name == "primary"
    assert gateway.cb.state == CircuitState.CLOSED
