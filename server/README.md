# Kadalu Server

Kadalu Server component, which runs glusterfsd and quotad.

## kadalu's QuotaD

This is a script which runs as a container (when kadalu is running in native mode), so that the required size is set as Quota for the PV directory. If kadalu uses external gluster storage, then this needs to be installed with `pip3 install kadalu-quotad`, and run on the machine which is exporting storage. If there are 3 nodes exporting storage (ie, hosting gluster bricks), then this needs to be running on all the 3 nodes.

