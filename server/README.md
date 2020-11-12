# Kadalu Server

Kadalu Server component, which runs glusterfsd and quotad.

## kadalu's QuotaD

This is a script which runs as a container (when kadalu is running in native mode), so that the required size is set as Quota for the PV directory.

## External Servers

In order for persistent volume claim resources.requests.storage limits to be enforced you must do the following:

* The gluster bricks **must** be provided from XFS volumes.
* The XFS volumes must be mounted with the prjquota option.
* For a single brick set the environment variable BRICK_PATH
_**or**_
* Set the environment variable BRICK_PATH=AUTO for automatic brick detection
_**or**_
* For one or more bricks list the bricks in /var/lib/glusterd/kadalu.info in the format expected by [quotad](kadalu_quotad/quotad.py)
* Install kadalu-quotad with `pip3 install kadalu-quotad`, and run on the machine which is exporting storage. If there are 3 nodes exporting storage (ie, hosting gluster bricks), then this needs to be running on all the 3 nodes.

If you don't do all of these things all volumes will have access to the full underlying brick size.

