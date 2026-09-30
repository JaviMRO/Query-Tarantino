from plan import configurations

CONFIGURATIONS_PER_LANGUAGE = 12 + 12 + 12 + 3 + 1 + 1


def test_a_round_with_download_has_every_configuration_of_the_three_languages() -> None:
    assert len(configurations(0)) == 3 * CONFIGURATIONS_PER_LANGUAGE


def test_download_only_runs_in_rounds_0_to_3() -> None:
    assert any(configuration[1] == "download" for configuration in configurations(3))
    assert not any(configuration[1] == "download" for configuration in configurations(4))
    assert len(configurations(4)) == 3 * (CONFIGURATIONS_PER_LANGUAGE - 1)


def test_the_same_round_always_gives_the_same_order() -> None:
    assert configurations(2) == configurations(2)


def test_each_round_shuffles_the_same_configurations_differently() -> None:
    assert configurations(1) != configurations(2)
    assert sorted(configurations(1)) == sorted(configurations(2))
