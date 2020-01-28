#!/bin/bash

#Deploy Kadalu Operator
echo -e "Do you want to deploy Kadalu or is it already deployed [y/n]"
read answer1
if [ $answer1 == 'y' ] ; then 

       sudo kubectl create -f https://kadalu.io/operator-latest.yaml
       echo "Kadalu Operator Deplyoed"

fi
#Create Storage Pool to the device, for future claims of this device
#Using kadalu kubectl plugin
echo -e "Do you want to create a Storage-Pool [y/n]"
read answer2

if [ $answer2 == 'y' ] ; then 

	echo -e "Enter the storage-pool name"
	#example storage-pool-1
	read storagePool
	
	echo -e "Enter the device/host name, for VM use minikube"
	read device
	#if using Virtual Machine , minikube
        
        echo -e "Do you already have a disk allocation, if yes enter complete path of device or Create a new truncated file [path/create]"
        read answer3
        
        if [ $answer3 == "path" ] ; then

		echo -e "Enter the device file path"
		read devPath

		#example /home/vatsa/tryKadalu/disk/test-storage
                sudo kubectl kadalu storage-add $storagePool --device $device:$devPath
	        echo "Storage Pool with name $storagePool created"
                
        else

	        echo -e "Enter the path of the device file to be created"
	        read dev
	        
	        echo -e "Enter the size of the truncated file in Ng or NNNm"
	        read devSize

	        sudo truncate -s $devSize $dev
                #kubectl kadalu storage-add $storagePool --device $device:/home/vatsa/trykadalu/disk/$dev
                sudo kubectl kadalu storage-add $storagePool --device $device:$dev
	        echo "Storage Pool with name $storagePool created"
        
        fi

	

fi


	echo "Checking Status of the Pods"
        
        #Status of Pods with Kadalu namespace.
	sudo kubectl get pods -n kadalu

	echo "Enter the name for the Pvc-File.yaml to be created"
	read pvcFileName
	echo "Enter the name of the PVC"
	read pvcName
	echo "Enter the storage value in NGi or NNNMi , N is number"
	read storageValue

	#Assuming the user clones the Kadalu dir, and executes this script from /extras/scripts dir.
        cp ../../examples/sample-pvc.yaml /tmp/${pvcFileName}.yaml


	sed -i s/pv1/$pvcName/  /tmp/${pvcFileName}.yaml 
	sed -i s/1Gi/$storageValue/  /tmp/${pvcFileName}.yaml 

	sudo kubectl create -f /tmp/${pvcFileName}.yaml
        
        #Since get pvc shows status as pending we can wait to halt the process for few seconds , example 100sec
        echo "Sleep 100s for status update"
        sleep 100
	sudo kubectl get pvc

	echo "Enter the name of the app.yaml"
	read podFileName
	echo "Enter the name of the Pod"
	read podName


        cp ../../examples/sample-app.yaml /tmp/${podFileName}.yaml
	sed -i s/pod1/$podName/  /tmp/${podFileName}.yaml
	sed -i s/pv1/$pvcName/  /tmp/${podFileName}.yaml
	sudo kubectl create -f /tmp/$podFileName.yaml
        
        echo "Sleep 100s for status update"
        sleep 100
 
        #Status of the Pod
        sudo kubectl get pods



    



