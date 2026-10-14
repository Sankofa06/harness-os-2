"""CRE-006's acceptance bar: a checkpoint found at multiple paths/hosts is
cataloged once (one `creative_assets` row, identified by content hash) with
multiple `creative_asset_locations` rows -- not once per path it happens to
sit at. Pure repository-level tests against a real in-memory SQLite DB
(the shared `db` fixture), no SSH involved.
"""

from __future__ import annotations

import pytest

from harness.core.domain import Host
from harness.core.ids import new_id
from harness.persistence.repos_control_plane import HostRepo
from harness.persistence.repos_creative_assets import CreativeAssetRepo
from harness.providers.creative.assets import ScannedAssetFile


async def _make_host(db, name: str) -> Host:
    host = Host(id=new_id("host"), display_name=name, kind="ssh", hostname="127.0.0.1")
    return await HostRepo(db).create(host)


@pytest.mark.asyncio
async def test_same_content_at_two_paths_on_one_host_is_one_asset_two_locations(db) -> None:
    host = await _make_host(db, "host-a")
    repo = CreativeAssetRepo(db)
    same_hash = "a" * 64

    await repo.record_scan(
        host.id,
        [
            ScannedAssetFile(
                path="/data/Models/StableDiffusion/model-a.safetensors",
                asset_kind="checkpoint",
                filename="model-a.safetensors",
                size_bytes=123,
                content_hash=same_hash,
            ),
            ScannedAssetFile(
                path="/data/Models/StableDiffusion/model-a-copy.safetensors",
                asset_kind="checkpoint",
                filename="model-a-copy.safetensors",
                size_bytes=123,
                content_hash=same_hash,
            ),
        ],
    )

    assets = await repo.list()
    assert len(assets) == 1
    locations = await repo.list_locations(assets[0].id)
    assert {loc.path for loc in locations} == {
        "/data/Models/StableDiffusion/model-a.safetensors",
        "/data/Models/StableDiffusion/model-a-copy.safetensors",
    }
    assert {loc.host_id for loc in locations} == {host.id}


@pytest.mark.asyncio
async def test_same_content_across_two_hosts_is_one_asset_with_both_locations(db) -> None:
    host_a = await _make_host(db, "host-a")
    host_b = await _make_host(db, "host-b")
    repo = CreativeAssetRepo(db)
    shared_hash = "b" * 64

    await repo.record_scan(
        host_a.id,
        [
            ScannedAssetFile(
                path="/data/Models/Lora/style.safetensors",
                asset_kind="lora",
                filename="style.safetensors",
                size_bytes=50,
                content_hash=shared_hash,
            )
        ],
    )
    await repo.record_scan(
        host_b.id,
        [
            ScannedAssetFile(
                path="/other/Models/Lora/style.safetensors",
                asset_kind="lora",
                filename="style.safetensors",
                size_bytes=50,
                content_hash=shared_hash,
            )
        ],
    )

    assets = await repo.list()
    assert len(assets) == 1
    locations = await repo.list_locations(assets[0].id)
    assert {loc.host_id for loc in locations} == {host_a.id, host_b.id}


@pytest.mark.asyncio
async def test_different_content_is_two_separate_assets(db) -> None:
    host = await _make_host(db, "host-a")
    repo = CreativeAssetRepo(db)

    await repo.record_scan(
        host.id,
        [
            ScannedAssetFile(
                path="/data/Models/VAE/vae-one.safetensors",
                asset_kind="vae",
                filename="vae-one.safetensors",
                size_bytes=10,
                content_hash="c" * 64,
            ),
            ScannedAssetFile(
                path="/data/Models/VAE/vae-two.safetensors",
                asset_kind="vae",
                filename="vae-two.safetensors",
                size_bytes=20,
                content_hash="d" * 64,
            ),
        ],
    )

    assets = await repo.list()
    assert len(assets) == 2
    assert {a.content_hash for a in assets} == {"c" * 64, "d" * 64}


@pytest.mark.asyncio
async def test_rescanning_a_path_with_changed_content_repoints_the_location(db) -> None:
    host = await _make_host(db, "host-a")
    repo = CreativeAssetRepo(db)
    path = "/data/Models/StableDiffusion/model.safetensors"

    await repo.record_scan(
        host.id,
        [
            ScannedAssetFile(
                path=path,
                asset_kind="checkpoint",
                filename="model.safetensors",
                size_bytes=100,
                content_hash="e" * 64,
            )
        ],
    )
    await repo.record_scan(
        host.id,
        [
            ScannedAssetFile(
                path=path,
                asset_kind="checkpoint",
                filename="model.safetensors",
                size_bytes=200,
                content_hash="f" * 64,
            )
        ],
    )

    assets = await repo.list()
    assert len(assets) == 2  # both the old and new content are still cataloged
    old_asset = next(a for a in assets if a.content_hash == "e" * 64)
    new_asset = next(a for a in assets if a.content_hash == "f" * 64)
    assert await repo.list_locations(old_asset.id) == []
    new_locations = await repo.list_locations(new_asset.id)
    assert [loc.path for loc in new_locations] == [path]


@pytest.mark.asyncio
async def test_asset_kind_filter(db) -> None:
    host = await _make_host(db, "host-a")
    repo = CreativeAssetRepo(db)
    await repo.record_scan(
        host.id,
        [
            ScannedAssetFile(
                path="/data/Models/Lora/a.safetensors",
                asset_kind="lora",
                filename="a.safetensors",
                size_bytes=1,
                content_hash="1" * 64,
            ),
            ScannedAssetFile(
                path="/data/Models/VAE/b.safetensors",
                asset_kind="vae",
                filename="b.safetensors",
                size_bytes=1,
                content_hash="2" * 64,
            ),
        ],
    )

    loras = await repo.list(asset_kind="lora")
    assert [a.canonical_filename for a in loras] == ["a.safetensors"]
