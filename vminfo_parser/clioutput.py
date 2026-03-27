import io
import sys
import typing as t
import weakref

import pandas as pd
from tabulate import tabulate


class CLIOutput:
    def __init__(self: t.Self) -> None:
        # Output buffer to store output.
        self.output = io.StringIO(initial_value="\n\n", newline="\n")

        # Finalizer for flushing buffer to stdout.
        # Will be called when self is deleted or when the interpreter exits
        self._finalize = weakref.finalize(self, self.flush_output, self.output)

        # might need to track the state of this object to ensure it's closed or not
        self._closed = False

    @staticmethod
    def flush_output(output: io.StringIO, file: io.TextIOBase | None = None) -> None:
        """Write StringIO Buffer to file (or stdout).  Closes output buffer.

        Args:
            output (io.StringIO): StringIO obj containing output buffer
            file (io.TextIOBase | None, optional): File to write butter to. Defaults to stdout.
        """
        if output.closed:
            return
        # Delay setting referece to stdout so tests can capture it
        if file is None:
            file = sys.stdout
        file.write(output.getvalue())
        output.close()

    def writeline(self: t.Self, line: t.Any = "") -> None:
        """write string to output buffer.  Adds newline if line does not end with one.

        Args:
            line (str, optional): string to write to output buffer. Defaults to "".
        """
        if self._closed:
            raise ValueError("CLIOutput is already closed")
        if not isinstance(line, str):
            line: str = str(line)
        if not line.endswith("\n"):
            line = line + "\n"
        self.write(line)

    def write(self: t.Self, line: t.Any) -> None:
        """Write string to output buffer.

        Args:
            line (str): string to write to output buffer
        """
        if self._closed:
            raise ValueError("CLIOutput is already closed")
        if not isinstance(line, str):
            line: str = str(line)
        self.output.write(line)

    def close(self: t.Self) -> None:
        """Calls private finalizer for output buffer.  Finalizer will be closed and cannot be called again."""
        if not self._closed:
            self._finalize()
            self._closed = True

    def format_dataframe_output(self: t.Self, dataFrame: pd.DataFrame, os_name: str | None = None) -> None:
        if dataFrame.index.nlevels == 2:
            pass
        else:
            count = dataFrame["Count"].values
            if count.size > 0:
                dataFrame = dataFrame.astype(str)
                table = tabulate(dataFrame, headers="keys", showindex=False, colalign=("left", "right"))
                self.writeline("")
                self.writeline(os_name)
                self.writeline(f"{'=' * len(os_name)}")
                self.writeline(table)

    def format_series_output(
        self: t.Self, counts: pd.Series, headers: list = "keys", table_format: str = "simple"
    ) -> None:
        df = pd.DataFrame(counts)
        table = tabulate(df, headers=headers, tablefmt=table_format)
        self.writeline(table)

    def print_formatted_disk_space(
        self: t.Self,
        dataFrame: pd.DataFrame,
        os_filter: str | None = None,
    ) -> None:
        """
        Print the formatted disk space information to the output.
        This function displays a header and the formatted data, optionally filtered by the operating system.

        Args:
            dataFrame (pd.DataFrame): A pandas DataFrame, likely sorted by disk space range but not necessarily
            os_filter (Optional[str]): An optional filter to display specific operating system information.

        Returns:
            None
        """
        self.writeline()
        # It looks inconsistent when using the OS version without making everything left justified
        # because sometimes the version is considered a string and sometimes its a num
        # so if OS Version is the name of  the index set the alignment
        if "OS Version" in dataFrame.index.name:
            table = tabulate(dataFrame, headers="keys", colalign=("left", "left", "center"))
        else:
            table = tabulate(dataFrame, headers="keys", numalign="center")
        if os_filter:
            self.writeline(os_filter)
            separator = "=" * len(os_filter)
            self.writeline(separator)
        self.writeline(table)
        self.writeline()

    def print_site_usage(self: t.Self, resource_list: list, dataFrame: pd.DataFrame) -> None:
        """
        Prints the site-wide usage of a specified resource, including Memory, CPU, Disk, or VM count.


        Args:
            resource_list (list): The type of resource to summarize. Options include "Memory", "CPU", "Disk", or "VM".
            dataFrame (pd.DataFrame): A DataFrame containing the relevant data for the site, including
                                      resource usage metrics.

        Returns:
            None: This function does not return a value; it prints the usage information directly to the console.
        """
        dataFrame = dataFrame.set_index("Site Name")
        self.writeline()
        for resource in resource_list:
            if not dataFrame.empty:
                match resource:
                    case "CPU":
                        cpu_usage = dataFrame["Site_CPU_Usage"].astype(int)
                        self.writeline(self.create_site_table(cpu_usage, ["Site Name", "Core Count"]))
                    case "Memory":
                        memory_usage = dataFrame["Site_RAM_Usage"].round(0).astype(int)
                        self.writeline(self.create_site_table(memory_usage, ["Site Name", "Memory Capacity (GB)"]))
                    case "Disk":
                        disk_usage = dataFrame["Site_Disk_Usage"]
                        self.writeline(self.create_site_table(disk_usage, ["Site Name", "Disk Capacity (TB)"]))
                    case "VM":
                        vm_count = dataFrame["Site_VM_Count"]
                        self.writeline(self.create_site_table(vm_count, ["Site Name", "VM Count"]))
                    case _:
                        self.writeline("No data available for the specified resource.")
            else:
                self.writeline("No data available for the specified resource.")
            self.writeline("")

    def create_site_table(self: t.Self, df: pd.DataFrame, headers: list, table_format: str = "simple") -> str:
        """Generate a formatted table from site data.

        This function takes a DataFrame containing site information and converts it into a
        string representation of a table with specified headers. The table is formatted for
        better readability.

        Args:
            df (pd.DataFrame): A DataFrame containing site data.
            headers (list): A list of headers for the table.

        Returns:
            str: A string representation of the formatted table.

        Examples:
            >>> df = pd.DataFrame({'Site A': [1], 'Site B': [2]})
            >>> create_site_table(df, ['Site', 'Value'])
            '  Site    Value\n-------  ------\nSite A      1\nSite B      2'
        """
        table_data = [[site, f"{value}"] for site, value in df.items()]
        return tabulate(table_data, headers=headers, numalign="center", tablefmt=table_format)

    def print_vm_density_summary(self: t.Self, site_df: pd.DataFrame) -> None:
        """Print site-level VM density summary table.

        Args:
            site_df (pd.DataFrame): DataFrame with site-level density statistics.
        """
        if site_df.empty:
            self.writeline("No site-level density data available.")
            return

        self.writeline()
        self.writeline("VM Density Summary by Site")
        self.writeline("=" * 26)
        display = site_df.rename(columns={
            "Total_VMs": "VMs",
            "Total_Hosts": "Hosts",
            "Total_Clusters": "Clusters",
            "Total_Cores": "Cores",
            "Avg_Density": "Avg VMs/Host",
            "Max_Density": "Max VMs/Host",
        })
        table = tabulate(display, headers="keys", showindex=False, numalign="center")
        self.writeline(table)
        self.writeline()

    def print_cluster_density(self: t.Self, cluster_df: pd.DataFrame) -> None:
        """Print per-cluster VM density breakdown.

        Args:
            cluster_df (pd.DataFrame): DataFrame with per-cluster density data.
        """
        if cluster_df.empty:
            self.writeline("No cluster density data available.")
            return

        self.writeline()
        self.writeline("VM Density by Cluster")
        self.writeline("=" * 21)
        display = cluster_df.rename(columns={
            "Total_VMs": "VMs",
            "Total_Cores": "Cores",
            "Avg_Density": "Avg VMs/Host",
            "Max_Density": "Max",
            "Min_Density": "Min",
            "Median_Density": "Median",
        })
        table = tabulate(display, headers="keys", showindex=False, numalign="center")
        self.writeline(table)
        self.writeline()

    def print_high_density_hosts(self: t.Self, hosts_df: pd.DataFrame) -> None:
        """Print hosts exceeding the high-density threshold.

        Args:
            hosts_df (pd.DataFrame): DataFrame of high-density hosts.
        """
        if hosts_df.empty:
            self.writeline()
            self.writeline("No hosts exceed the high-density threshold (50 VMs).")
            self.writeline()
            return

        self.writeline()
        self.writeline(f"High-Density Hosts (>= 50 VMs): {len(hosts_df)} hosts")
        self.writeline("=" * 40)
        display_cols = [c for c in ["Host", "Cluster", "Site Name", "# VMs", "# Cores"] if c in hosts_df.columns]
        table = tabulate(hosts_df[display_cols], headers="keys", showindex=False, numalign="center")
        self.writeline(table)
        self.writeline()

    def print_nic_distribution(self: t.Self, nic_df: pd.DataFrame, zero_nic_count: int = 0) -> None:
        """Print NIC count distribution table.

        Args:
            nic_df (pd.DataFrame): DataFrame with NIC distribution data.
            zero_nic_count (int): Number of VMs excluded due to having 0 NICs.
        """
        if nic_df.empty:
            self.writeline("No NIC distribution data available.")
            return

        self.writeline()
        self.writeline("NIC Distribution (VM count grouped by number of attached virtual NICs)")
        self.writeline("=" * 71)

        if "Site Name" in nic_df.columns:
            for site in nic_df["Site Name"].unique():
                site_data = nic_df[nic_df["Site Name"] == site][["NICs", "Count", "Pct"]]
                self.writeline(f"\n{site}")
                self.writeline("-" * len(site))
                table = tabulate(site_data, headers="keys", showindex=False, numalign="center")
                self.writeline(table)
        else:
            table = tabulate(nic_df, headers="keys", showindex=False, numalign="center")
            self.writeline(table)

        if zero_nic_count > 0:
            self.writeline()
            self.writeline(
                f"Note: {zero_nic_count} VMs with 0 NICs were excluded "
                "(likely templates or incomplete VMs)."
            )
        self.writeline()
