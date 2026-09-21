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


class TestOvercommitAnalysis:
    """Tests for CPU/memory overcommit analysis methods."""

    @pytest.fixture
    def host_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Host": ["h1", "h2", "h3"],
            "Cluster": ["C1", "C1", "C2"],
            "# Cores": [16, 32, 24],
            "# Memory": [131072, 262144, 196608],
            "Site Name": ["SiteA", "SiteA", "SiteB"],
        })

    @pytest.fixture
    def vm_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Host": ["h1", "h1", "h1", "h2", "h2", "h3", "h3", "h3", "h3"],
            "CPUs": [4, 4, 8, 8, 8, 4, 4, 4, 4],
            "Memory": [4096, 4096, 8192, 16384, 16384, 2048, 2048, 2048, 2048],
            "OS according to the configuration file": ["Win"] * 9,
            "OS according to the VMware Tools": ["Win"] * 9,
            "Environment": ["Prod"] * 9,
            "Provisioned MiB": [100] * 9,
        })

    @pytest.fixture
    def overcommit_analyzer(self, mock_config: MockType, host_df: pd.DataFrame, vm_df: pd.DataFrame) -> Analyzer:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = host_df
        vm_data.df = vm_df
        vm_data.column_headers = {"vCPU": "CPUs", "vmMemory": "Memory"}
        return Analyzer(vm_data, mock_config)

    def test_overcommit_by_host(self, overcommit_analyzer: Analyzer) -> None:
        result = overcommit_analyzer.get_overcommit_by_host()
        assert len(result) == 3

        h1 = result[result["Host"] == "h1"].iloc[0]
        assert h1["Total_vCPU"] == 16
        assert h1["# Cores"] == 16
        assert h1["CPU_Overcommit"] == 1.0
        # h1: 3 VMs with Memory [4096, 4096, 8192] = 16384 MiB = 16 GiB
        # h1 physical: 131072 MB = 128 GiB
        assert h1["Total_VM_Memory_GiB"] == 16384
        assert h1["Physical_Memory_GiB"] == 128.0
        assert h1["Mem_Overcommit"] == round(16384 / 128.0, 2)

        h2 = result[result["Host"] == "h2"].iloc[0]
        assert h2["Total_vCPU"] == 16
        assert h2["CPU_Overcommit"] == 0.5

        h3 = result[result["Host"] == "h3"].iloc[0]
        assert h3["Total_vCPU"] == 16
        assert round(h3["CPU_Overcommit"], 2) == 0.67

    def test_overcommit_by_host_no_host_df(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = None
        a = Analyzer(vm_data, mock_config)
        assert a.get_overcommit_by_host().empty

    def test_overcommit_by_host_missing_cores(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = pd.DataFrame({"Host": ["h1"], "Cluster": ["C1"]})
        vm_data.df = pd.DataFrame({"Host": ["h1"], "CPUs": [4]})
        vm_data.column_headers = {"vCPU": "CPUs"}
        a = Analyzer(vm_data, mock_config)
        assert a.get_overcommit_by_host().empty

    def test_overcommit_by_host_missing_host_in_vinfo(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = pd.DataFrame({"Host": ["h1"], "# Cores": [16]})
        vm_data.df = pd.DataFrame({"CPUs": [4]})
        vm_data.column_headers = {"vCPU": "CPUs"}
        a = Analyzer(vm_data, mock_config)
        assert a.get_overcommit_by_host().empty

    def test_overcommit_by_cluster(self, overcommit_analyzer: Analyzer) -> None:
        result = overcommit_analyzer.get_overcommit_by_cluster()
        assert len(result) == 2
        assert "CPU_Overcommit" in result.columns

        c1 = result[result["Cluster"] == "C1"].iloc[0]
        assert c1["Total_vCPU"] == 32
        assert c1["Physical_Cores"] == 48
        assert round(c1["CPU_Overcommit"], 2) == 0.67

        c2 = result[result["Cluster"] == "C2"].iloc[0]
        assert c2["Total_vCPU"] == 16
        assert c2["Physical_Cores"] == 24
        assert round(c2["CPU_Overcommit"], 2) == 0.67

    def test_overcommit_by_site(self, overcommit_analyzer: Analyzer) -> None:
        result = overcommit_analyzer.get_overcommit_by_site()
        assert len(result) == 2
        assert "CPU_Overcommit" in result.columns

        site_a = result[result["Site Name"] == "SiteA"].iloc[0]
        assert site_a["Total_vCPU"] == 32
        assert site_a["Physical_Cores"] == 48
        assert round(site_a["CPU_Overcommit"], 2) == 0.67

    def test_overcommit_by_site_no_site_column(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = pd.DataFrame({
            "Host": ["h1", "h2"],
            "Cluster": ["C1", "C1"],
            "# Cores": [16, 32],
            "# Memory": [131072, 262144],
        })
        vm_data.df = pd.DataFrame({
            "Host": ["h1", "h2"],
            "CPUs": [8, 16],
            "Memory": [4096, 8192],
        })
        vm_data.column_headers = {"vCPU": "CPUs", "vmMemory": "Memory"}
        a = Analyzer(vm_data, mock_config)
        result = a.get_overcommit_by_site()
        assert len(result) == 1
        assert result.iloc[0]["Site Name"] == "All"
        assert result.iloc[0]["Total_vCPU"] == 24
        assert result.iloc[0]["Physical_Cores"] == 48
        assert result.iloc[0]["CPU_Overcommit"] == 0.5

    def test_overcommit_host_with_zero_vms(self, mock_config: MockType) -> None:
        vm_data = NonCallableMagicMock()
        vm_data.host_df = pd.DataFrame({
            "Host": ["h1", "h2"],
            "Cluster": ["C1", "C1"],
            "# Cores": [16, 32],
        })
        vm_data.df = pd.DataFrame({
            "Host": ["h1"],
            "CPUs": [8],
        })
        vm_data.column_headers = {"vCPU": "CPUs"}
        a = Analyzer(vm_data, mock_config)
        result = a.get_overcommit_by_host()
        assert len(result) == 2
        h2 = result[result["Host"] == "h2"].iloc[0]
        assert h2["Total_vCPU"] == 0
        assert h2["CPU_Overcommit"] == 0.0
