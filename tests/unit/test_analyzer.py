from collections.abc import Generator
from unittest.mock import NonCallableMagicMock

import pandas as pd
import pytest
from pytest_mock import MockFixture, MockType

import vminfo_parser.const as vm_const
from vminfo_parser.analyzer import Analyzer


@pytest.fixture
def analyzer(mock_config: MockType, mock_vmdata: MockType) -> Generator[Analyzer, None, None]:
    yield Analyzer(mock_vmdata, mock_config)


@pytest.mark.parametrize("os_names", [["os1"], ["os1,os2"]], ids=["single", "multiple"])
def test_by_os(analyzer: Analyzer, mocker: MockFixture, os_names: list[str]) -> None:
    test_func: MockType = mocker.MagicMock()
    mock_unique_os = mocker.patch.object(analyzer, attribute="get_unique_os_names")
    mock_unique_os.return_value = os_names

    analyzer.by_os(test_func)

    mock_unique_os.assert_called_once()
    assert test_func.call_count == len(os_names)
    test_func.assert_has_calls([((os_name,), {}) for os_name in os_names])


@pytest.mark.parametrize(
    "df_data,os_name,expected",
    [
        ({"OS Name": ["os1", "os2"]}, "os1", ["os1"]),
        ({"OS Name": ["os1", "os2"]}, None, ["os1", "os2"]),
        ({"OS Name": ["os1", "os2", ""]}, None, ["os1", "os2"]),
        ({"OS Name": ["os1", "os2", None]}, None, ["os1", "os2"]),
        ({"OS Name": ["os1", "os2"]}, "os3", []),
        ({"OS Name": ["", None]}, None, []),
    ],
    ids=[
        "os_name_filter",
        "no_os_name_filter",
        "empty_os_name_field",
        "null_os_name_field",
        "os_name_filter_not_in_data",
        "all_invalid_os_names",
    ],
)
def test_get_unique_os_names(analyzer: Analyzer, df_data: dict, os_name: str | None, expected: list[str]) -> None:
    analyzer.vm_data.df = pd.DataFrame(data=df_data)
    analyzer.config.os_name = os_name

    response = analyzer.get_unique_os_names()

    assert response == expected


def test_get_os_counts(analyzer: Analyzer, mocker: MockFixture) -> None:
    mock_df = analyzer.vm_data.create_environment_filtered_dataframe.return_value
    mock_calculate = mocker.patch.object(analyzer, "_calculate_os_counts")

    response = analyzer.get_operating_system_counts()

    analyzer.vm_data.create_environment_filtered_dataframe.assert_called_once_with(
        analyzer.config.environments, env_filter=analyzer.config.environment_filter
    )
    mock_calculate.assert_called_once_with(mock_df)

    assert response == mock_calculate.return_value


def test_get_os_counts_for_os_name(analyzer: Analyzer, mocker: MockFixture) -> None:
    mock_df: MockType = analyzer.vm_data.create_environment_filtered_dataframe.return_value
    mock_calculate: MockType = mocker.patch.object(analyzer, "_calculate_os_counts")
    analyzer.config.os_name = "os1"
    mock_filtered_df: MockType = mock_df.__getitem__.return_value

    response = analyzer.get_operating_system_counts()

    mock_df.__getitem__.assert_has_calls(
        [
            ("", ("OS Name",)),
            ("", (False,)),
        ],
        any_order=True,
    )
    mock_filtered_df.__eq__.assert_called_once_with(analyzer.config.os_name)

    analyzer.vm_data.create_environment_filtered_dataframe.assert_called_once_with(
        analyzer.config.environments, env_filter=analyzer.config.environment_filter
    )
    mock_calculate.assert_called_once_with(mock_filtered_df)

    assert response == mock_calculate.return_value


def test_get_supported_os_counts(analyzer: Analyzer, mocker: MockFixture) -> None:
    mock_calculate = mocker.patch.object(analyzer, "_calculate_os_counts")
    mock_count_df = mock_calculate.return_value
    mock_env_df = analyzer.vm_data.create_environment_filtered_dataframe.return_value
    mock_filtered_df = mock_env_df.__getitem__.return_value

    response = analyzer.get_supported_os_counts()

    # Assert create_environment_filtered_dataframe called correctly
    analyzer.vm_data.create_environment_filtered_dataframe.assert_called_once_with(
        analyzer.config.environments, env_filter=analyzer.config.environment_filter
    )

    # Assert counts filtered by supported os set from const
    mock_filtered_df.isin.assert_called_once_with(vm_const.SUPPORTED_OSES)
    mock_env_df.__getitem__.assert_has_calls(
        [
            ("", ("OS Name",), {}),
            ("", (mock_filtered_df.isin.return_value,), {}),
        ],
        any_order=True,
    )

    # Assert _calculate_os_counts called correctly
    mock_calculate.assert_called_once_with(mock_filtered_df)

    # Assert correct value is returned
    assert response == mock_count_df


def test_get_unsupported_os_counts(analyzer: Analyzer, mocker: MockFixture) -> None:
    mock_calculate = mocker.patch.object(analyzer, "_calculate_os_counts")
    mock_count_df = mock_calculate.return_value
    mock_env_df = analyzer.vm_data.create_environment_filtered_dataframe.return_value
    mock_filtered_df = mock_env_df.__getitem__.return_value

    response = analyzer.get_supported_os_counts()

    # Assert create_environment_filtered_dataframe called correctly
    analyzer.vm_data.create_environment_filtered_dataframe.assert_called_once_with(
        analyzer.config.environments, env_filter=analyzer.config.environment_filter
    )

    # Assert counts filtered by supported os set from const
    mock_filtered_df.isin.assert_called_once_with(vm_const.SUPPORTED_OSES)
    mock_env_df.__getitem__.assert_has_calls(
        [
            ("", ("OS Name",), {}),
            ("", (mock_filtered_df.isin.return_value,), {}),  # mock ignores the ~ negation that is performed by pandas
        ],
        any_order=True,
    )

    # Assert _calculate_os_counts called correctly
    mock_calculate.assert_called_once_with(mock_filtered_df)

    # Assert correct value is returned
    assert response == mock_count_df


class TestVMDensityAnalysis:
    """Tests for the VM density analysis methods."""

    @pytest.fixture
    def host_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Host": ["h1", "h2", "h3", "h4"],
            "Cluster": ["C1", "C1", "C2", "C2"],
            "# VMs": [30, 40, 55, 60],
            "# Cores": [16, 32, 24, 48],
            "# Memory": [128, 256, 192, 384],
            "Site Name": ["SiteA", "SiteA", "SiteB", "SiteB"],
        })

    @pytest.fixture
    def density_analyzer(self, mock_config: MockType, host_df: pd.DataFrame) -> Analyzer:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = host_df
        vm_data.df = pd.DataFrame({"NICs": [1, 1, 2, 1, 3], "Site Name": ["SiteA"] * 3 + ["SiteB"] * 2})
        return Analyzer(vm_data, mock_config)

    def test_get_vm_density_by_host(self, density_analyzer: Analyzer) -> None:
        result = density_analyzer.get_vm_density_by_host()
        assert len(result) == 4
        assert "# VMs" in result.columns
        assert "Site Name" in result.columns

    def test_get_vm_density_by_host_no_host_df(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = None
        a = Analyzer(vm_data, mock_config)
        result = a.get_vm_density_by_host()
        assert result.empty

    def test_get_vm_density_by_cluster(self, density_analyzer: Analyzer) -> None:
        result = density_analyzer.get_vm_density_by_cluster()
        assert len(result) == 2
        assert "Total_VMs" in result.columns
        assert "Avg_Density" in result.columns

        c2 = result[result["Cluster"] == "C2"].iloc[0]
        assert c2["Total_VMs"] == 115
        assert c2["Hosts"] == 2

    def test_get_vm_density_by_site(self, density_analyzer: Analyzer) -> None:
        result = density_analyzer.get_vm_density_by_site()
        assert len(result) == 2
        site_b = result[result["Site Name"] == "SiteB"].iloc[0]
        assert site_b["Total_VMs"] == 115
        assert site_b["Total_Hosts"] == 2

    def test_get_nic_distribution(self, density_analyzer: Analyzer) -> None:
        result, zero_count = density_analyzer.get_nic_distribution()
        assert not result.empty
        assert "NICs" in result.columns
        assert "Count" in result.columns
        assert "Pct" in result.columns
        assert zero_count == 0

    def test_get_nic_distribution_no_nics_column(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = None
        vm_data.df = pd.DataFrame({"Other": [1, 2, 3]})
        a = Analyzer(vm_data, mock_config)
        result, zero_count = a.get_nic_distribution()
        assert result.empty
        assert zero_count == 0

    def test_get_nic_distribution_excludes_zero_nics(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = None
        vm_data.df = pd.DataFrame({
            "NICs": [0, 0, 1, 1, 2, 0],
            "Site Name": ["S1"] * 6,
        })
        a = Analyzer(vm_data, mock_config)
        result, zero_count = a.get_nic_distribution()
        assert zero_count == 3
        assert 0 not in result["NICs"].values
        assert set(result["NICs"].values) == {1, 2}

    def test_get_high_density_hosts(self, density_analyzer: Analyzer) -> None:
        result = density_analyzer.get_high_density_hosts(threshold=50)
        assert len(result) == 2
        assert result.iloc[0]["# VMs"] == 60

    def test_get_high_density_hosts_none_above(self, density_analyzer: Analyzer) -> None:
        result = density_analyzer.get_high_density_hosts(threshold=100)
        assert result.empty
