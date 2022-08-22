"""
controller server implementation
"""
import logging
import random
import time

import grpc

from kadalu.csi import csi_pb2
from kadalu.csi import csi_pb2_grpc
from kadalu.common.utils import logf
from kadalu.csi.volumeutils import (PersistentVolume, Pool, PvException,
                                    yield_list_of_pvcs, SINGLE_NODE_WRITER,
                                    MULTI_NODE_MULTI_WRITER)

# Generator to be used in ListVolumes
GEN = None

# Rate limiting number of PVCs returned per request of ListVolumes if CO
# doesn't mention any max_entries
LIMIT = 30


def validate_create_volume_request(request, context):
    """Validate the Volume Create request"""
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
    pvol = PersistentVolume.search_by_name(request.name)
    if pvol.pool is not None:
        if pvol.size != request.capacity_range.required_bytes:
            errmsg = ("Failed to create PV with same name with "
                      f"different capacity (Existing: {pvol.size}, "
                      f"Requested: {request.capacity_range.required_bytes})")
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            return csi_pb2.CreateVolumeResponse()

    return None


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

        err = validate_create_volume_request(request, context)
        if err is not None:
            return err

        pv_req = PersistentVolume.from_csi_request(request)

        if not pv_req.valid_block_access_mode():
            # Multi node writer is not allowed for PV_TYPE_VIRTBLOCK/PV_TYPE_RAWBLOCK
            errmsg = "Only SINGLE_NODE_WRITER is allowed for block Volume"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.CreateVolumeResponse()

        logging.debug(logf(
            "Found PV type",
            pvtype=pv_req.type,
            capabilities=request.volume_capabilities
        ))

        pools = Pool.list(filters=pv_req.sc_parameters)
        logging.debug(logf(
            "Got filtered list of Pools for the PV",
            pools=",".join(p.name for p in pools),
            pv=pv_req.name
        ))

        # Select any one Pool for provisioning the PV
        # Randomize the entries so we can issue PV from different storage pool
        # It is possible to enhance this step to sort the Storage pools based
        # on the available size and select the Pool that has more space.
        random.shuffle(pools)

        # From the list of Pools available, select and assign a Pool based
        # on size availability.
        pv_req.mount_and_select_pool(pools)
        if pv_req.pool is None:
            errmsg = "No Storage Pools available for the PV request"
            logging.error(logf(errmsg, pv_name=pv_req.name))
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return csi_pb2.CreateVolumeResponse()

        # TODO: Handle Error
        try:
            pvol = PersistentVolume.create(pv_req)
        except PvException as ex:
            context.set_details(ex)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.CreateVolumeResponse()
        finally:
            if pv_req.sc_parameters["single_pv_per_pool"]:
                # If 'kadalu_format' is 'non-native', the request will be
                # considered as to map 1 PV to 1 Gluster volume

                # No need to keep the mount on controller
                pv_req.pool.unmount()

        logging.info(logf(
            "PV created",
            name=request.name,
            pv_type=pvol.type,
            size=pvol.size,
            pool_name=pvol.pool.name,
            duration_seconds=time.time() - start_time
        ))
        return csi_pb2.CreateVolumeResponse(
            volume={
                "volume_id": pvol.name,
                "capacity_bytes": pvol.size,
                "volume_context": pvol.to_volume_context()
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

        pvol = PersistentVolume.search_by_name(request.volume_id)
        if pvol.pool is None:
            logging.warning(logf(
                "PV not found for delete",
                pv_name=pvol.name
            ))

        if pvol.pool is not None:
            pvol.delete()

        logging.info(logf(
            "Delete Volume response completed",
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

        pvol = PersistentVolume.search_by_name(request.volume_id)
        if pvol.pool is None:
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

        modes = [SINGLE_NODE_WRITER, MULTI_NODE_MULTI_WRITER]

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
        global GEN
        # Need to check for no hostvol creation only once
        if GEN is None:
            # Handle no pool creation, with ~10s timeout
            pools = Pool.list(iteration=3)
            if not pools:
                errmsg = "No Pool is created yet"
                logging.error(errmsg)
                context.set_details(errmsg)
                context.set_code(grpc.StatusCode.ABORTED)
                return csi_pb2.ListVolumesResponse()

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
            max_entries = request.max_entries or 0
            if not max_entries:
                # In worst case limit ourselves with custom max_entries and
                # set next_token
                max_entries = LIMIT
            GEN = yield_list_of_pvcs(max_entries)

        # Run and wait for 'send'
        try:
            next(GEN)
        except StopIteration as errmsg:
            # Handle no PVC created from a storage volume yet
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.ABORTED)
            return csi_pb2.ListVolumesResponse()

        try:
            # Get list of PVCs limited at max_entries by suppling the token
            pvcs, next_token = GEN.send(starting_token)
        except StopIteration as errmsg:
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.ABORTED)
            return csi_pb2.ListVolumesResponse()

        entries = [{
            "volume": {
                "volume_id": value.get("name"),
                "capacity_bytes": value.get("size"),
            }
        } for value in pvcs if value is not None]

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
        logging.debug(logf(
            "Expand Volume request",
            request=request
        ))

        if not request.volume_id:
            errmsg = "Volume ID is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ControllerExpandVolumeResponse()

        if not request.capacity_range:
            errmsg = "Capacity Range is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ControllerExpandVolumeResponse()

        if not request.capacity_range.required_bytes:
            errmsg = "Required Bytes is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ControllerExpandVolumeResponse()

        expansion_requested_pvsize = request.capacity_range.required_bytes

        # Get existing volume
        pvol = PersistentVolume.search_by_name(request.volume_id)
        if pvol.pool is None:
            errmsg = logf(
                "Unable to find volume",
                volume_id=request.volume_id
            )
            logging.error(errmsg)
            context.set_details(str(errmsg))
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.ControllerExpandVolumeResponse()

        if pvol.pool.single_pv_per_pool:
            errmsg = "PV with kadalu_format == non-native doesn't support Expansion"
            logging.error(errmsg)
            # But lets not fail the call, and continue here
            return csi_pb2.ControllerExpandVolumeResponse()

        # Volume size before expansion
        logging.info(logf(
            "Existing PV size and Expansion requested PV size",
            existing_pvsize=pvol.size,
            expansion_requested_pvsize=expansion_requested_pvsize
        ))

        logging.debug(logf(
            "Found PV type",
            pvtype=pvol.type,
            capability=request.volume_capability
        ))

        # Check free-size in storage-pool before expansion
        if not pvol.pool.is_size_available(expansion_requested_pvsize):
            logging.error(logf(
                "Storage Pool is full. Add more storage",
                pool_name=pvol.pool.name
            ))
            errmsg = "Storage Pool resource is exhausted"
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return csi_pb2.CreateVolumeResponse()

        try:
            pvol.expand(expansion_requested_pvsize)
        except PvException as ex:
            context.set_details(ex)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.CreateVolumeResponse()

        logging.info(logf(
            "Volume expanded",
            name=pvol.name,
            size=expansion_requested_pvsize,
            pool_name=pvol.pool.name,
            pvtype=pvol.type,
            volpath=pvol.path,
            duration_seconds=time.time() - start_time
        ))

        # send_analytics_tracker("pvc-%s" % hostvoltype, uid)
        return csi_pb2.ControllerExpandVolumeResponse(
            capacity_bytes=int(expansion_requested_pvsize)
        )
