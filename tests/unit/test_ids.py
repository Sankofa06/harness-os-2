from harness.core.ids import is_valid_id, new_id


def test_new_id_has_prefix_and_valid_format() -> None:
    value = new_id("run")
    assert value.startswith("run_")
    assert is_valid_id(value, "run")


def test_new_id_rejects_unknown_prefix() -> None:
    import pytest

    with pytest.raises(ValueError):
        new_id("bogus")


def test_ids_sort_by_creation_time() -> None:
    earlier = new_id("run", timestamp_ms=1_000)
    later = new_id("run", timestamp_ms=2_000)
    assert earlier < later


def test_is_valid_id_rejects_garbage() -> None:
    assert not is_valid_id("not-an-id")
    assert not is_valid_id("run_tooshort")
    assert not is_valid_id(new_id("run"), prefix="host")
