# How it works?

kadalu project uses glusterfs to export the given storage as PV, and provide mounts to users. All this is made possible by the evolving of kubernetes's operator framework and CSI driver developments.

The deployment of CSI driver, and gluster server (or brick) processes are handled by kadalu operator. Once deployed, kadalu operator keeps watching for changes to a config file with kind 'kadaluStorage'.

When kadalu is deployed, glusterfs is hidden behind the scene, and users needn't know about glusterfs at all. The CSI driver provides all further APIs to manage the storage volumes, and mounts.

