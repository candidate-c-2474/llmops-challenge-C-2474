import pytest
from inference_gateway import FakeBackend, InferenceGateway, InferenceRequest, CircuitState

@pytest.mark.asyncio
async def test_gateway_fallback_on_failure():
    class FailingBackend(FakeBackend):
        async def generate(self, request):
            raise RuntimeError("Primary backend unavailable")

    primary = FailingBackend(name="primary")
    fallback = FakeBackend(name="fallback", default_response="Fallback OK")
    gateway = InferenceGateway(primary=primary, fallback=fallback)

    req = InferenceRequest(messages=[{"role": "user", "content": "test"}])
    res = await gateway.generate(req)
    assert res.content == "Fallback OK"
    assert res.backend_name == "fallback"
