from harness.core.control_plane import ControlPlaneResource, ResourceHealth
from harness.providers.language.fake import FakeProvider


def test_fake_provider_implements_control_plane_resource() -> None:
    provider = FakeProvider()
    assert isinstance(provider, ControlPlaneResource)


def test_describe_reports_declared_capabilities_and_settings_schema() -> None:
    provider = FakeProvider()
    descriptor = provider.describe()

    assert descriptor.id == "fake"
    assert descriptor.type == "language_provider"
    assert "L0_CHAT" in descriptor.capabilities
    assert descriptor.health == ResourceHealth.OK
    assert descriptor.settings_schema is not None
    assert "common" in descriptor.settings_schema
