"""
controller server implementation
"""
import os
import logging
import time

import grpc

import csi_pb2
import csi_pb2_grpc
from volumeutils import mount_and_select_hosting_volume, \
    create_virtblock_volume, create_subdir_volume, delete_volume, \
    get_pv_hosting_volumes, PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK, \
    HOSTVOL_MOUNTDIR, check_external_volume
from kadalulib import logf


class ControllerServer(csi_pb2_grpc.ControllerServicer):
    """
    ControllerServer object is responsible for handling host
    volume mount and PV creation.
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """
    def CreateVolume(self, request, context):
        start_time = time.time()
        logging.debug(logf(
            "Create Volume request",
            request=request
        ))
        pvsize = request.capacity_range.required_bytes

        pvtype = PV_TYPE_SUBVOL
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

        ext_volume = None
        if filters['hostvol_type'] == 'External':
            ext_volume = check_external_volume(request)
            if ext_volume:
                logging.info(logf(
                    "Volume (External) created",
                    name=request.name,
                    size=pvsize,
                    hostvol=ext_volume['name'],
                    pvtype=pvtype,
                    volpath=ext_volume['host'],
                    duration_seconds=time.time() - start_time
                ))
                return csi_pb2.CreateVolumeResponse(
                    volume={
                        "volume_id": request.name,
                        "capacity_bytes": pvsize,
                        "volume_context": {
                            "type": "External",
                            "hostvol": ext_volume['name'],
                            "pvtype": pvtype,
                            "gserver": ext_volume['host'],
                            "fstype": "xfs",
                            "options": ext_volume['options'],
                        }
                    }
                )

            logging.debug(logf(
                "Here as checking external volume failed",
                external_volume=ext_volume
            ))
            errmsg = "External Storage provided not valid"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return csi_pb2.CreateVolumeResponse()


        host_volumes = get_pv_hosting_volumes(filters)
        logging.debug(logf(
            "Got list of hosting Volumes",
            volumes=",".join(host_volumes)
        ))

        hostvol = mount_and_select_hosting_volume(host_volumes, pvsize)
        if hostvol is None:
            errmsg = "No Hosting Volumes available, add more storage"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return csi_pb2.CreateVolumeResponse()

        if pvtype == PV_TYPE_VIRTBLOCK:
            vol = create_virtblock_volume(
                os.path.join(HOSTVOL_MOUNTDIR, hostvol),
                request.name, pvsize)
        else:
            vol = create_subdir_volume(
                os.path.join(HOSTVOL_MOUNTDIR, hostvol),
                request.name, pvsize)

        logging.info(logf(
            "Volume created",
            name=request.name,
            size=pvsize,
            hostvol=hostvol,
            pvtype=pvtype,
            volpath=vol.volpath,
            duration_seconds=time.time() - start_time
        ))
        return csi_pb2.CreateVolumeResponse(
            volume={
                "volume_id": request.name,
                "capacity_bytes": pvsize,
                "volume_context": {
                    "type": filters['hostvol_type'],
                    "hostvol": hostvol,
                    "pvtype": pvtype,
                    "path": vol.volpath,
                    "fstype": "xfs"
                }
            }
        )

    def DeleteVolume(self, request, context):
        start_time = time.time()
        delete_volume(request.volume_id)
        logging.info(logf(
            "Volume deleted",
            name=request.volume_id,
            duration_seconds=time.time() - start_time
        ))
        return csi_pb2.DeleteVolumeResponse()

    def ValidateVolumeCapabilities(self, request, context):
        # TODO
        pass

    def ListVolumes(self, request, context):
        # TODO
        # Mount hostvol
        # Listdir and return the list
        # Volume capacity need to be stored somewhere
        pass

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
                }
            ]
        )
