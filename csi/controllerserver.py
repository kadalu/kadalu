"""
controller server implementation
"""
import json
import logging
import os
import random
import time

import grpc

import csi_pb2
import csi_pb2_grpc
from kadalulib import logf, send_analytics_tracker
from volumeutils import (HOSTVOL_MOUNTDIR, PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK,
                         check_external_volume, create_subdir_volume,
                         create_virtblock_volume, delete_volume, expand_volume,
                         get_pv_hosting_volumes, is_hosting_volume_free,
                         mount_and_select_hosting_volume, search_volume,
                         unmount_glusterfs, update_free_size,
                         update_subdir_volume, update_virtblock_volume,
                         yield_list_of_pvcs)

VOLINFO_DIR = "/var/lib/gluster"
KADALU_VERSION = os.environ.get("KADALU_VERSION", "latest")

# Generator to be used in ListVolumes
GEN = None

# Rate limiting number of PVCs returned per request of ListVolumes if CO
# doesn't mention any max_entries
LIMIT = 30


class ControllerServer(csi_pb2_grpc.ControllerServicer):
    """
    ControllerServer object is responsible for handling host
    volume mount and PV creation.
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """

    # noqa # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    def CreateVolume(self, request, context):
        start_time = time.time()
        logging.debug(logf(
            "Create Volume request",
            request=request
        ))

        if not request.name:
            errmsg = "Volume name is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.CreateVolumeResponse()

        if not request.volume_capabilities:
            errmsg = "Volume Capabilities is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.CreateVolumeResponse()

        # Check for same name and different capacity
        volume = search_volume(request.name)
        if volume:
            if volume.size != request.capacity_range.required_bytes:
                errmsg = "Failed to create volume with same name with different capacity"
                logging.error(errmsg)
                context.set_details(errmsg)
                context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                return csi_pb2.CreateVolumeResponse()

        pvsize = request.capacity_range.required_bytes

        pvtype = PV_TYPE_SUBVOL
        # 'latest' finds a place here, because only till 0.5.0 version
        # we had 'latest' as a separate version. After that, 'latest' is
        # just a link to latest version.
        if KADALU_VERSION in ["0.5.0", "0.4.0", "0.3.0"]:
            for vol_capability in request.volume_capabilities:
                # using getattr to avoid Pylint error
                single_node_writer = getattr(csi_pb2.VolumeCapability.AccessMode,
                                             "SINGLE_NODE_WRITER")

                if vol_capability.access_mode.mode == single_node_writer:
                    pvtype = PV_TYPE_VIRTBLOCK

        logging.debug(logf(
            "Found PV type",
            pvtype=pvtype,
            capabilities=request.volume_capabilities
        ))

        # TODO: Check the available space under lock

        # Add everything from parameter as filter item
        filters = {}
        for pkey, pvalue in request.parameters.items():
            filters[pkey] = pvalue

        logging.debug(logf(
            "Filters applied to choose storage",
            **filters
        ))

        # UID is stored at the time of installation in configmap.
        uid = None
        with open(os.path.join(VOLINFO_DIR, "uid")) as uid_file:
            uid = uid_file.read()

        host_volumes = get_pv_hosting_volumes(filters)
        logging.debug(logf(
            "Got list of hosting Volumes",
            volumes=",".join(v['name'] for v in host_volumes)
        ))
        hostvol = None
        ext_volume = None
        data = {}
        hostvoltype = filters.get("hostvol_type", None)
        if not hostvoltype:
            # This means, the request came on 'kadalu' storage class type.

            # Randomize the entries so we can issue PV from different storage
            random.shuffle(host_volumes)

            hostvol = mount_and_select_hosting_volume(host_volumes, pvsize)
            if hostvol is None:
                errmsg = "No Hosting Volumes available, add more storage"
                logging.error(errmsg)
                context.set_details(errmsg)
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                return csi_pb2.CreateVolumeResponse()

            info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % hostvol)
            with open(info_file_path) as info_file:
                data = json.load(info_file)

            hostvoltype = data['type']

        if hostvoltype == 'External':
            ext_volume = check_external_volume(request, host_volumes)

            if ext_volume:
                mntdir = os.path.join(HOSTVOL_MOUNTDIR, ext_volume['name'])

                if not filters.get('kadalu-format', None):
                    # No need to keep the mount on controller
                    unmount_glusterfs(mntdir)

                    logging.info(logf(
                        "Volume (External) created",
                        name=request.name,
                        size=pvsize,
                        mount=mntdir,
                        hostvol=ext_volume['g_volname'],
                        pvtype=pvtype,
                        volpath=ext_volume['g_host'],
                        duration_seconds=time.time() - start_time
                    ))

                    send_analytics_tracker("pvc-external", uid)
                    return csi_pb2.CreateVolumeResponse(
                        volume={
                            "volume_id": request.name,
                            "capacity_bytes": pvsize,
                            "volume_context": {
                                "type": hostvoltype,
                                "hostvol": ext_volume['name'],
                                "pvtype": pvtype,
                                "gvolname": ext_volume['g_volname'],
                                "gserver": ext_volume['g_host'],
                                "fstype": "xfs",
                                "options": ext_volume['g_options'],
                            }
                        }
                    )

                # The external volume should be used as kadalu host vol

                if not is_hosting_volume_free(ext_volume['name'], pvsize):

                    logging.error(logf(
                        "Hosting volume is full. Add more storage",
                        volume=ext_volume['name']
                    ))
                    errmsg = "External resource is exhausted"
                    context.set_details(errmsg)
                    context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                    return csi_pb2.CreateVolumeResponse()

                if pvtype == PV_TYPE_VIRTBLOCK:
                    vol = create_virtblock_volume(
                        mntdir, request.name, pvsize)
                else:
                    vol = create_subdir_volume(
                        mntdir, request.name, pvsize)

                logging.info(logf(
                    "Volume created",
                    name=request.name,
                    size=pvsize,
                    hostvol=ext_volume['name'],
                    pvtype=pvtype,
                    volpath=vol.volpath,
                    duration_seconds=time.time() - start_time
                ))

                send_analytics_tracker("pvc-external-kadalu", uid)
                # Pass required argument to get mount working on
                # nodeplugin through volume_context
                return csi_pb2.CreateVolumeResponse(
                    volume={
                        "volume_id": request.name,
                        "capacity_bytes": pvsize,
                        "volume_context": {
                            "type": hostvoltype,
                            "hostvol": ext_volume['name'],
                            "pvtype": pvtype,
                            "path": vol.volpath,
                            "gvolname": ext_volume['g_volname'],
                            "gserver": ext_volume['g_host'],
                            "fstype": "xfs",
                            "options": ext_volume['g_options'],
                        }
                    }
                )

            # If external volume not found
            logging.debug(logf(
                "Here as checking external volume failed",
                external_volume=ext_volume
            ))
            errmsg = "External Storage provided not valid"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.CreateVolumeResponse()

        if not hostvol:
            # Randomize the entries so we can issue PV from different storage
            random.shuffle(host_volumes)

            hostvol = mount_and_select_hosting_volume(host_volumes, pvsize)
            if hostvol is None:
                errmsg = "No Hosting Volumes available, add more storage"
                logging.error(errmsg)
                context.set_details(errmsg)
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                return csi_pb2.CreateVolumeResponse()

        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)
        if pvtype == PV_TYPE_VIRTBLOCK:
            vol = create_virtblock_volume(
                mntdir, request.name, pvsize)
        else:
            vol = create_subdir_volume(
                mntdir, request.name, pvsize)

        logging.info(logf(
            "Volume created",
            name=request.name,
            size=pvsize,
            hostvol=hostvol,
            pvtype=pvtype,
            volpath=vol.volpath,
            duration_seconds=time.time() - start_time
        ))

        update_free_size(hostvol, request.name, -pvsize)

        send_analytics_tracker("pvc-%s" % hostvoltype, uid)
        return csi_pb2.CreateVolumeResponse(
            volume={
                "volume_id": request.name,
                "capacity_bytes": pvsize,
                "volume_context": {
                    "type": hostvoltype,
                    "hostvol": hostvol,
                    "pvtype": pvtype,
                    "path": vol.volpath,
                    "fstype": "xfs"
                }
            }
        )

    def DeleteVolume(self, request, context):
        start_time = time.time()

        if not request.volume_id:
            errmsg = "Volume ID is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.DeleteVolumeResponse()

        delete_volume(request.volume_id)
        logging.info(logf(
            "Volume deleted",
            name=request.volume_id,
            duration_seconds=time.time() - start_time
        ))
        return csi_pb2.DeleteVolumeResponse()

    def ValidateVolumeCapabilities(self, request, context):

        if not request.volume_id:
            errmsg = "Volume ID is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ValidateVolumeCapabilitiesResponse()

        if not search_volume(request.volume_id):
            errmsg = "Requested volume does not exist"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return csi_pb2.ValidateVolumeCapabilitiesResponse()

        if not request.volume_capabilities:
            errmsg = "Volume Capabilities is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ValidateVolumeCapabilitiesResponse()

        volume_id = request.volume_id
        volume_capabilities = request.volume_capabilities

        logging.info(logf(
            "Validating Volume capabilities for volume",
            volume_id=volume_id,
            volume_capabilities=volume_capabilities
        ))

        single_node_writer = getattr(csi_pb2.VolumeCapability.AccessMode,
                                     "SINGLE_NODE_WRITER")

        multi_node_multi_writer = getattr(csi_pb2.VolumeCapability.AccessMode,
                                          "MULTI_NODE_MULTI_WRITER")

        modes = [single_node_writer, multi_node_multi_writer]

        for volume_capability in volume_capabilities:
            if volume_capability.access_mode.mode not in modes:

                errmsg = "Requested volume capability not supported"
                logging.error(errmsg)
                context.set_details(errmsg)
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return csi_pb2.ValidateVolumeCapabilitiesResponse()

        return csi_pb2.ValidateVolumeCapabilitiesResponse(
            confirmed={
                "volume_capabilities": volume_capabilities,
            }
        )



    def ListVolumes(self, request, context):
        """Returns list of all PVCs with sizes existing in Kadalu Storage"""

        logging.debug(logf("ListVolumes request received", request=request))
        starting_token = request.starting_token or '0'
        try:
            starting_token = int(starting_token)
        except ValueError as errmsg:
            # We are using tokens which can be converted to integer's
            errmsg = "Invalid starting token supplied"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.ABORTED)
            return csi_pb2.ListVolumesResponse()

        if not request.starting_token:
            # This is the first call and so start the generator
            global GEN
            max_entries = request.max_entries or 0
            if not max_entries:
                # In worst case limit ourselves with custom max_entries and
                # set next_token
                max_entries = LIMIT
            GEN = yield_list_of_pvcs(max_entries)

        # Run and wait for 'send'
        next(GEN)
        try:
            # Get list of PVCs limited at max_entries by suppling the token
            pvcs, next_token = GEN.send(starting_token)
        except StopIteration as errmsg:
            errmsg = errmsg.args[0] or "Runtime Error while getting PVCs list"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.ABORTED)
            return csi_pb2.ListVolumesResponse()

        entries = [{
            "volume": {
                "volume_id": value[0],
                "capacity_bytes": value[1]
            }
        } for value in pvcs]

        return csi_pb2.ListVolumesResponse(entries=entries,
                                           next_token=next_token)

    def ControllerGetCapabilities(self, request, context):
        # using getattr to avoid Pylint error
        capability_type = getattr(
            csi_pb2.ControllerServiceCapability.RPC, "Type").Value

        return csi_pb2.ControllerGetCapabilitiesResponse(
            capabilities=[
                {
                    "rpc": {
                        "type": capability_type("CREATE_DELETE_VOLUME")
                    }
                },
                {
                    "rpc": {
                        "type": capability_type("LIST_VOLUMES")
                    }
                },
                {
                    "rpc": {
                        "type": capability_type("EXPAND_VOLUME")
                    }
                }
            ]
        )

    def ControllerExpandVolume(self, request, context):
        """
        Controller plugin RPC call implementation of EXPAND_VOLUME
        """

        start_time = time.time()

        if not request.volume_id:
            errmsg = "Volume ID is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ControllerExpandVolumeResponse()

        expansion_requested_pvsize = request.capacity_range.required_bytes

        # Get existing volume
        existing_volume = search_volume(request.volume_id)

        # Volume size before expansion
        existing_pvsize = existing_volume.size
        pvname = existing_volume.volname

        logging.info(logf(
            "Existing PV size and Expansion requested PV size",
            existing_pvsize=existing_pvsize,
            expansion_requested_pvsize=expansion_requested_pvsize
        ))

        pvtype = PV_TYPE_SUBVOL
        single_node_writer = getattr(csi_pb2.VolumeCapability.AccessMode,
                                     "SINGLE_NODE_WRITER")

        if request.volume_capability.AccessMode == single_node_writer:
            pvtype = PV_TYPE_VIRTBLOCK

        logging.debug(logf(
            "Found PV type",
            pvtype=pvtype,
            capability=request.volume_capability
        ))

        hostvol = existing_volume.hostvol
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)

        # Check free-size in storage-pool before expansion
        if not is_hosting_volume_free(hostvol, expansion_requested_pvsize):

            logging.error(logf(
                "Hosting volume is full. Add more storage",
                volume=hostvol
            ))
            errmsg = "Host volume resource is exhausted"
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return csi_pb2.CreateVolumeResponse()

        if pvtype == PV_TYPE_VIRTBLOCK:
            update_virtblock_volume(
                mntdir, pvname, expansion_requested_pvsize)
            expand_volume(mntdir)
        else:
            update_subdir_volume(
                mntdir, pvname, expansion_requested_pvsize)

        logging.info(logf(
            "Volume expanded",
            name=pvname,
            size=expansion_requested_pvsize,
            hostvol=hostvol,
            pvtype=pvtype,
            volpath=existing_volume.volpath,
            duration_seconds=time.time() - start_time
        ))

        # sizechanged is the additional change to be
        # subtracted from storage-pool
        sizechange = expansion_requested_pvsize - existing_pvsize
        update_free_size(hostvol, pvname, -sizechange)

        # if not hostvoltype:
        #     hostvoltype = "unknown"

        # send_analytics_tracker("pvc-%s" % hostvoltype, uid)
        return csi_pb2.ControllerExpandVolumeResponse(
            capacity_bytes=int(expansion_requested_pvsize)
        )
