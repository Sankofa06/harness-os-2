import pytest

from harness.core.domain import Host, ModelProfile, ProviderConfig
from harness.core.errors import ConflictError, NotFoundError
from harness.core.ids import new_id
from harness.persistence.repos_control_plane import HostRepo, ModelProfileRepo, ProviderConfigRepo


@pytest.mark.asyncio
async def test_provider_config_round_trip(db) -> None:
    repo = ProviderConfigRepo(db)
    config = await repo.create(
        ProviderConfig(
            id=new_id("prov"),
            type="openai_compatible",
            display_name="Local LM Studio",
            base_url="http://127.0.0.1:1234/v1",
            settings={"common": {"temperature": 0.2}},
        )
    )
    fetched = await repo.get(config.id)
    assert fetched.display_name == "Local LM Studio"
    assert fetched.settings["common"]["temperature"] == 0.2

    listed = await repo.list()
    assert config.id in {c.id for c in listed}


@pytest.mark.asyncio
async def test_provider_config_duplicate_name_rejected(db) -> None:
    repo = ProviderConfigRepo(db)
    await repo.create(ProviderConfig(id=new_id("prov"), type="fake", display_name="dup"))
    with pytest.raises(ConflictError):
        await repo.create(ProviderConfig(id=new_id("prov"), type="fake", display_name="dup"))


@pytest.mark.asyncio
async def test_provider_config_not_found(db) -> None:
    repo = ProviderConfigRepo(db)
    with pytest.raises(NotFoundError):
        await repo.get("prov_missing")


@pytest.mark.asyncio
async def test_provider_config_set_enabled(db) -> None:
    repo = ProviderConfigRepo(db)
    config = await repo.create(
        ProviderConfig(id=new_id("prov"), type="fake", display_name="toggle-me")
    )
    updated = await repo.set_enabled(config.id, False)
    assert updated.enabled is False


@pytest.mark.asyncio
async def test_host_round_trip_with_capabilities(db) -> None:
    repo = HostRepo(db)
    host = await repo.create(
        Host(
            id=new_id("host"),
            display_name="build-box",
            kind="ssh",
            hostname="203.0.113.10",
            port=22,
            username="dev",
            workspace_roots=["/home/dev/projects"],
            capabilities=["ssh_execution", "filesystem", "git"],
        )
    )
    fetched = await repo.get(host.id)
    assert fetched.workspace_roots == ["/home/dev/projects"]
    assert set(fetched.capabilities) == {"ssh_execution", "filesystem", "git"}


@pytest.mark.asyncio
async def test_host_update_capabilities(db) -> None:
    repo = HostRepo(db)
    host = await repo.create(Host(id=new_id("host"), display_name="node-box", kind="node"))
    updated = await repo.set_capabilities(host.id, ["gpu_telemetry", "full_telemetry"])
    assert set(updated.capabilities) == {"gpu_telemetry", "full_telemetry"}


@pytest.mark.asyncio
async def test_host_duplicate_display_name_rejected(db) -> None:
    repo = HostRepo(db)
    await repo.create(Host(id=new_id("host"), display_name="dup-host", kind="local"))
    with pytest.raises(ConflictError):
        await repo.create(Host(id=new_id("host"), display_name="dup-host", kind="local"))


@pytest.mark.asyncio
async def test_model_profile_round_trip(db) -> None:
    providers = ProviderConfigRepo(db)
    provider = await providers.create(
        ProviderConfig(id=new_id("prov"), type="fake", display_name="profile-repo-provider")
    )
    repo = ModelProfileRepo(db)
    profile = await repo.create(
        ModelProfile(
            id=new_id("prof"),
            name="repo-profile",
            provider_config_id=provider.id,
            model_id="fake-mini",
            settings={"common": {"temperature": 0.3}},
            load_policy="always_loaded",
            placement_policy="prefer-fastest",
            tool_capability_policy="required",
        )
    )
    fetched = await repo.get(profile.id)
    assert fetched.load_policy == "always_loaded"
    assert fetched.placement_policy == "prefer-fastest"
    assert fetched.settings["common"]["temperature"] == 0.3

    listed = await repo.list()
    assert profile.id in {p.id for p in listed}

    await repo.delete(profile.id)
    with pytest.raises(NotFoundError):
        await repo.get(profile.id)
