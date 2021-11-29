"""
Storage Add alternate syntax parser
"""
TYPE_KEYWORD = 0
NUMBER = 1
STORAGE_UNIT = 2

TYPE_KEYWORDS = [
    "replica",
    "mirror",
    "disperse",
    "disperse-data",
    "redundancy",
    "arbiter",
    "external"
]


class InvalidVolumeCreateRequest(Exception):
    """Raise when the Volume Create request is not valid"""



# noqa # pylint: disable=too-few-public-methods
class Token:
    """Token Structure"""
    def __init__(self, kind, value):
        self.kind = kind
        self.value = value


# noqa # pylint: disable=too-few-public-methods
class VolumeCreateRequest:
    """Volume Create Request"""
    def __init__(self):
        self.distribute_groups = []


# noqa # pylint: disable=too-few-public-methods
class VolumeCreateRequestDistributeGroup:
    """Distribute Group"""
    def __init__(self):
        self.storage_units = []
        self.replica_count = 0
        self.arbiter_count = 0
        self.disperse_count = 0
        self.redundancy_count = 0
        self.external_count = 0
        self.replica_keyword = ""


def next_token(tokens):
    """Get next item from the iterator else return None"""
    try:
        return next(tokens)
    except StopIteration:
        return None


def tokenizer(args):
    """
    Split input arguments into Tokens.
    """
    tokens = []

    for arg in args:
        if arg in TYPE_KEYWORDS:
            tokens.append(Token(TYPE_KEYWORD, arg))
            continue

        try:
            int(arg)
            tokens.append(Token(NUMBER, arg))
            continue
        except ValueError:
            pass

        tokens.append(Token(STORAGE_UNIT, arg))

    return tokens


def disperse_and_redundancy_count(disperse, data, redundancy):
    """
    Any two counts available out of three, return
    only normalized disperse and redundancy count.
    """
    if data > 0 and redundancy > 0:
        return (data + redundancy, redundancy)

    if data > 0 and disperse > 0:
        return (disperse, disperse - data)

    return (disperse, redundancy)


def get_subvol_size(counts):
    """
    Count based grouping when storage units list is provided as
    separate list and count is specified with the keyword.
    For example: `replica 3 H1:S1 H2:S2 H3:S3 H4:S4 H5:S5 H6:S6`
    """
    if counts["replica"] > 0 or counts["mirror"] > 0:
        return counts["replica"] + counts["mirror"] + counts["arbiter"]

    if counts["disperse"] > 0 or counts["disperse-data"] > 0 or \
       counts["redundancy"] > 0:
        disp_count, _ = disperse_and_redundancy_count(
            counts["disperse"],
            counts["disperse-data"],
            counts["redundancy"]
        )
        return disp_count

    return 1


def split_list(storage_units, subvol_size):
    """Split the list of Storage units based on Subvol size"""
    for idx in range(0, len(storage_units), subvol_size):
        yield storage_units[idx:idx + subvol_size]


def replica_keyword(replica_count, mirror_count):
    """Replica volume can be created using `replica` or `mirror` keyword."""
    if replica_count > 0:
        return "replica"

    if mirror_count > 0:
        return "mirror"

    return ""


def distribute_group_count_based(counts, storage_units):
    """
    Split the given storage units into list of distribute
    groups based on replica/disperse count.
    """
    subvol_size = get_subvol_size(counts)
    for grp_storage_units in split_list(storage_units, subvol_size):
        dist_group = VolumeCreateRequestDistributeGroup()
        dist_group.storage_units = grp_storage_units
        dist_group.replica_count = counts["replica"] + counts["mirror"]
        dist_group.arbiter_count = counts["arbiter"]
        dist_group.disperse_count, dist_group.redundancy_count = \
            disperse_and_redundancy_count(
                counts["disperse"],
                counts["disperse-data"],
                counts["redundancy"]
            )
        dist_group.replica_keyword = replica_keyword(
            counts["replica"],
            counts["mirror"]
        )
        yield dist_group


def different_type_exists(storage_units, current_keyword):
    """
    If one type of distribute group is already parsed, it is
    now time to start new distribute group. Return true if a
    different type of distribute group already exists.
    """
    if current_keyword in ["replica", "mirror", "arbiter"]:
        disperse_related_count = len(storage_units["disperse"]) + \
            len(storage_units["redundancy"]) + \
            len(storage_units["disperse-data"])

        if disperse_related_count > 0:
            return True

    if current_keyword in ["disperse", "disperse-data", "redundancy"]:
        replica_related_count = len(storage_units["replica"]) + \
            len(storage_units["mirror"]) + len(storage_units["arbiter"])

        if replica_related_count > 0:
            return True

    return False


def distribute_group(storage_units, current_keyword):
    """
    When parser encounters the type keyword or at the end of the
    parsing, find out one distribute group is already parsed or not.
    Return None if parsing of a distribute group is not complete else
    return the distribute group object.
    """
    if current_keyword is not None and \
       len(storage_units[current_keyword]) == 0 and \
       not different_type_exists(storage_units, current_keyword):
        return None

    dist_group = VolumeCreateRequestDistributeGroup()

    if current_keyword is None and len(storage_units["external"]) > 0:
        dist_group.storage_units = storage_units["external"]
        dist_group.external_count = len(storage_units["external"])
    elif len(storage_units["replica"]) > 0 or len(storage_units["mirror"]) > 0:
        dist_group.storage_units = storage_units["replica"] + \
            storage_units["mirror"] + storage_units["arbiter"]
        dist_group.replica_count = len(storage_units["replica"]) + \
            len(storage_units["mirror"])
        dist_group.arbiter_count = len(storage_units["arbiter"])
        dist_group.replica_keyword = replica_keyword(
            len(storage_units["replica"]),
            len(storage_units["mirror"])
        )
    elif len(storage_units["disperse"]) > 0 or \
         len(storage_units["disperse-data"]) > 0:
        dist_group.storage_units = storage_units["disperse"] + \
            storage_units["disperse-data"] + storage_units["redundancy"]
        dist_group.disperse_count, dist_group.redundancy_count = \
            disperse_and_redundancy_count(
                len(storage_units["disperse"]),
                len(storage_units["disperse-data"]),
                len(storage_units["redundancy"])
            )
    else:
        return None

    return dist_group


def reset_storage_units():
    """
    Reset the Storage units object before parsing
    each distribute group
    """
    return {
        "replica": [],
        "mirror": [],
        "arbiter": [],
        "disperse": [],
        "disperse-data": [],
        "redundancy": [],
        "external": []
    }


# noqa # pylint: disable=too-many-branches
def parser(tokens):
    """
    Parse each tokens and construct the Volume Create Request
    """
    req = VolumeCreateRequest()
    tokens_iter = iter(tokens)
    token = next_token(tokens_iter)

    counts = {
        "replica": 0,
        "mirror": 0,
        "arbiter": 0,
        "disperse": 0,
        "disperse-data": 0,
        "redundancy": 0
    }
    storage_units = reset_storage_units()
    all_storage_units = []
    skip_token_next = False

    while True:
        if token is None:
            break

        if token.kind == TYPE_KEYWORD:
            keyword = token.value
            dist_group = distribute_group(storage_units, keyword)
            if dist_group is not None:
                req.distribute_groups.append(dist_group)
                storage_units = reset_storage_units()

            while True:
                token = next_token(tokens_iter)

                if token is None:
                    break

                if token.kind == STORAGE_UNIT:
                    storage_units[keyword].append(token.value)
                    continue

                if token.kind == NUMBER:
                    counts[keyword] = int(token.value)
                else:
                    skip_token_next = True

                break
        elif token.kind == STORAGE_UNIT:
            all_storage_units.append(token.value)

        if not skip_token_next:
            skip_token_next = False
            token = next_token(tokens_iter)

    dist_group = distribute_group(storage_units, None)
    if dist_group is not None:
        req.distribute_groups.append(dist_group)

    if len(all_storage_units) > 0:
        req.distribute_groups = list(distribute_group_count_based(
            counts, all_storage_units
        ))

    return req


def validate(req):
    """
    Validate the Volume create request after parsing
    """
    for dist_grp in req.distribute_groups:
        if dist_grp.replica_count > 0 and \
           len(dist_grp.storage_units) != dist_grp.replica_count:
            raise InvalidVolumeCreateRequest(
                "Number of Storage units not matching "
                f"{dist_grp.replica_keyword} count"
            )
        if dist_grp.disperse_count > 0 and \
           len(dist_grp.storage_units) != dist_grp.disperse_count:
            raise InvalidVolumeCreateRequest(
                "Number of Storage units not matching disperse count"
            )


def volume_type(req):
    """Find Volume Type based on the first distribute Group"""
    dist_grp_1 = req.distribute_groups[0]
    if dist_grp_1.replica_count == 2:
        return "Replica2"

    if dist_grp_1.replica_count == 3:
        return "Replica3"

    if dist_grp_1.disperse_count == 3:
        return "Disperse"

    if dist_grp_1.external_count > 0:
        return "External"

    return "Replica1"


def get_all_storage_units(req):
    """Return only the list of Storage Units from the request"""
    storage_units = []
    for dist_grp in req.distribute_groups:
        storage_units += dist_grp.storage_units

    return storage_units
