import yaml
from datetime import datetime
from clioutput import CLIOutput
from tabulate import tabulate


class Output:
    def __init__(self):
        self.cli_output = CLIOutput()

    def migration_output(self, migrations: list, type_of_migration: str) -> None:
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


def main():
    with open("somefile.yaml", "r") as yaml_file:
        mtv_plan_data = yaml.safe_load(yaml_file)
    output = Output()
    successful_migrations = []
    failed_migrations = []
    for entry in mtv_plan_data["items"]:
        if "completed" in entry["status"]["migration"].keys():
            start_time = datetime.fromisoformat(entry["status"]["migration"]["started"])
            end_time = datetime.fromisoformat(entry["status"]["migration"]["completed"])
            # Calculate duration
            duration = end_time - start_time
            number_of_vms = len(entry["spec"]["vms"])
            vms_failed = False
            for vms in entry["status"]["migration"]["vms"]:
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
            print()

    output.migration_output(failed_migrations, "failed")
    output.migration_output(successful_migrations, "successful")
    output.cli_output.close()


if __name__ == "__main__":
    main()
