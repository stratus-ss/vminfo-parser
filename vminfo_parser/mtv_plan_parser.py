import yaml
from datetime import datetime
from clioutput import CLIOutput
from tabulate import tabulate


class Output:
    def __init__(self):
        self.cli_output = CLIOutput()

    def migration_plan_output(self, migrations: list, type_of_migration: str) -> None:
        rows = []
        number_of_migrations = len(migrations)
        average_time = sum(item["total_duration_mins"] for item in migrations) / number_of_migrations
        total_number_of_vms = sum(item["vms"] for item in migrations)
        max_minutes = max(item["total_duration_mins"] for item in migrations)
        min_minutes = min(item["total_duration_mins"] for item in migrations)
        header = f"The number of {type_of_migration} migrations:"
        sep = "-" * len(header)
        rows.append([header, number_of_migrations])
        rows.append([sep])
        rows.append(["The number of vms:", total_number_of_vms])
        rows.append(["Longest runtime in minutes: ", f"{max_minutes:.1f}"])
        rows.append(["Shortest runtime in minutes: ", f"{min_minutes:.1f}"])
        rows.append(["Average runtime in minutes: ", f"{average_time:.1f}"])
        table = tabulate(rows, tablefmt="plain")

        self.cli_output.write(table)
        self.cli_output.write("\n\n")

    def group_vms_by_os(self, vm_attributes):
        vm_groups = {}
        for vm_id, attributes in vm_attributes.items():
            os = attributes["os"]
            if os not in vm_groups:
                vm_groups[os] = []
            vm_groups[os].append(attributes)
        return vm_groups

    def vm_migration_output(self, vm_attributes: dict) -> None:
        grouped_vms = self.group_vms_by_os(vm_attributes)

        for vm_os, attributes in grouped_vms.items():
            rows = []
            number_of_vms = len(attributes)
            average_disk_size = (sum(item["total_disk_sizes"] for item in attributes) / 1024) / number_of_vms
            average_migration_time = sum(item["migration_minutes"] for item in attributes) / number_of_vms
            largest_vm = max(item["total_disk_sizes"] for item in attributes) / 1024
            smallest_vm = min(item["total_disk_sizes"] for item in attributes) / 1024
            max_minutes = max(item["migration_minutes"] for item in attributes)
            min_minutes = min(item["migration_minutes"] for item in attributes)
            header = f"{vm_os} hosts:"
            sep = "-" * len(header)
            rows.append([header, number_of_vms])
            rows.append([sep])
            rows.append(["Longest transfer in minutes: ", f"{max_minutes:.1f}"])
            rows.append(["Largest transfer size in GB: ", f"{largest_vm:.1f}"])
            rows.append(["Shortest runtime in minutes: ", f"{min_minutes:.1f}"])
            rows.append(["Smallest transfer size in GB: ", f"{smallest_vm:.1f}"])
            rows.append(["Average runtime in minutes: ", f"{average_migration_time:.1f}"])
            rows.append(["Average transfer size in GB: ", f"{average_disk_size:.1f}"])
            table = tabulate(rows, tablefmt="plain")
            self.cli_output.write(table)
            self.cli_output.write("\n\n")


class Processing:
    def __init__(self) -> None:
        pass

    def extract_vmid_to_os_name(self, file_object: str) -> dict:
        with open("some.yaml", "r") as yaml_file:
            vm_data = yaml.safe_load(yaml_file)
        my_dict = {}
        for line in vm_data["items"]:
            try:
                vmID = line["metadata"]["labels"]["vmID"]
                vm_name = line["metadata"]["name"]
                vm_UID = line["metadata"]["uid"]
                vm_os = line["spec"]["template"]["metadata"]["annotations"]["vm.kubevirt.io/os"]
                my_dict[vmID] = {"name": vm_name, "uid": vm_UID, "os": vm_os}
            except:
                print(f"key missing, skipping entry {line['metadata']['name']}")
        return my_dict


def main():
    with open("some.yaml", "r") as yaml_file:
        mtv_plan_data = yaml.safe_load(yaml_file)
    output = Output()
    processing = Processing()
    vm_attributes = processing.extract_vmid_to_os_name("test")
    successful_migrations = []
    failed_migrations = []
    for entry in mtv_plan_data["items"]:
        if "completed" in entry["status"]["migration"].keys():
            plan_start_time = datetime.fromisoformat(entry["status"]["migration"]["started"])
            plan_end_time = datetime.fromisoformat(entry["status"]["migration"]["completed"])
            # Calculate duration
            duration = plan_end_time - plan_start_time
            number_of_vms = len(entry["spec"]["vms"])
            vms_failed = False
            for vms in entry["status"]["migration"]["vms"]:
                vm_id = vms["id"]
                disk_sizes = 0
                for item in vms["pipeline"]:
                    if "annotations" in item.keys():
                        disk_sizes += item["progress"]["total"]
                vm_duration = (plan_end_time - plan_start_time).total_seconds() / 60
                if vm_id in vm_attributes.keys():
                    vm_attributes[vm_id].update({"migration_minutes": vm_duration})
                    vm_attributes[vm_id].update({"total_disk_sizes": disk_sizes})
                for vm in vms["conditions"]:
                    if vm["type"] != "Succeeded":
                        vms_failed = True
            migration_dict = {
                "name": entry["metadata"]["name"],
                "total_duration_mins": duration.total_seconds() / 60,
                "vms": number_of_vms,
                "vms_failed": f"{vms_failed}",
            }
            if vms_failed:
                failed_migrations.append(migration_dict)
            else:
                successful_migrations.append(migration_dict)
    output.vm_migration_output(vm_attributes)
    output.migration_plan_output(failed_migrations, "failed")
    output.migration_plan_output(successful_migrations, "successful")
    output.cli_output.close()


if __name__ == "__main__":
    main()
