"""
Utilities for reading information from gluster for 'external' quotad
"""
import os
try:
    from glustercli.cli import volume
except ImportError:
    volume = None

KADALU_PATHS = {'info', 'subvol'}
UUID_FILE = "/var/lib/glusterd/glusterd.info"

MYUUID = None

def get_node_id():
    """
    Returns the local glusterd's UUID
    """
    global MYUUID

    if MYUUID is not None:
        return MYUUID

    val = None
    with open(UUID_FILE) as uuid_file:
        for line in uuid_file:
            if line.startswith("UUID="):
                val = line.strip().split("=")[-1]
                break

    MYUUID = val
    return val


def get_automatic_bricks():
    """
    Returns array of paths to gluster bricks hosted on _this_ server
    that appear to contain kadalu data and are therefore worth crawling
    """
    if not volume:
        return []

    local_uuid = get_node_id()
    found_bricks = []
    for vol in volume.vollist():
        for brick in volume.info(vol)[0]['bricks']:
            if brick['uuid'] != local_uuid:
                continue
            brick_path = brick['name'].partition(':')[2]
            is_kadalu_brick = True
            for kadalu_path in KADALU_PATHS:
                if not os.path.isdir(brick_path + '/' + kadalu_path):
                    is_kadalu_brick = False
                    break
            if is_kadalu_brick:
                found_bricks.append(brick_path)

    return found_bricks
