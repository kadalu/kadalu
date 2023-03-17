""" Utils for server component """

import copy
import kadalu_volgen

DEFAULT_OPTIONS = {
    "performance.client-io-threads": "off",
    "performance.stat-prefetch": "off",
    "performance.quick-read": "off",
    "performance.open-behind": "off",
    "performance.read-ahead": "off",
    "performance.io-cache": "off",
    "performance.readdir-ahead": "off"
}

def generate_client_volgen_data(data):
    """
    Create and return client volgen data, which is parsed by
    Kadalu Volgen library for creation of Client &
    Self-Heal Daemon(SHD) volfiles.

    Client volgen data is created by calculating number of distribute
    groups and storage units in each distribute group.
    Then slicing bricks data(Created using storgae pool info based on configmap)
    into respective distribute groups.
    """

    # No of distribute groups in a volume
    dist_grp_count = 0
    # No of storage units in a distribute group
    storage_unit_count = 0
    replica_count = 0

    get_replica_count = {
        "Replica1" : 1,
        "Replica2" : 2,
        "Replica3" : 3
    }

    if data["type"] == "Disperse":
        storage_unit_count = data["disperse"]["data"] + data["disperse"]["redundancy"]
        replica_count = 0
    else:
        storage_unit_count = replica_count = get_replica_count.get(data["type"], "")

    client_data = {}
    client_data["name"] = data["volname"]
    client_data["id"] = data["volume_id"]

    dist_grp_count = int((len(data["bricks"]) / storage_unit_count))
    client_data["distribute_groups"] = [{} for _ in range(dist_grp_count)]

    for dist_grp_idx, dist_grp in enumerate(client_data["distribute_groups"]):
        if "Replica" in data["type"]:
            dist_grp["type"] = "replicate"
        else:
            dist_grp["type"] = "disperse"

        if replica_count:
            dist_grp["replica_count"] = replica_count
        if dist_grp["type"] == "disperse":
            dist_grp["disperse_count"] = data["disperse"].get("data", 0)
            dist_grp["redundancy_count"] = data["disperse"].get("redundancy", 0)

        dist_grp["storage_units"] = [{} for _ in range(storage_unit_count)]

        for storage_unit_idx, storage_unit in enumerate(dist_grp["storage_units"]):
            brick_idx = (dist_grp_idx * storage_unit_count + storage_unit_idx)
            storage_unit["path"] = data["bricks"][brick_idx].get("brick_path", "")
            storage_unit["port"] = 24007
            storage_unit["node"] = {
                "name" : data["bricks"][brick_idx].get("node", ""),
                "id" : data["bricks"][brick_idx].get("node_id", "")
            }

    return client_data

def generate_brick_volfile(storage_unit, storage_unit_volfile_path):
    """ Generate brick/storage_unit volfile using Kadalu Volgen library"""

    kadalu_volgen.generate(
        "/var/lib/kadalu/templates/storage_unit.vol.j2",
        data=storage_unit,
        output_file=storage_unit_volfile_path
    )


def generate_shd_volfile(data, shd_volfile_path):
    """ Generate Self-Heal-Daemon(SHD) volfile using Kadalu Volgen library"""

    client_data = generate_client_volgen_data(data)

    kadalu_volgen.generate(
        "/var/lib/kadalu/templates/shd.vol.j2",
        data=client_data,
        output_file=shd_volfile_path
    )


def generate_client_volfile(data, client_volfile_path):
    """ Generate client volfile using Kadalu Volgen library"""

    options = copy.copy(DEFAULT_OPTIONS)
    client_data = generate_client_volgen_data(data)

    kadalu_volgen.generate(
        "/var/lib/kadalu/templates/client.vol.j2",
        data=client_data,
        options=options,
        output_file=client_volfile_path
    )
