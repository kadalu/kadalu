# KUBERNETES - Installation guide for ubuntu 18.04 LTS


## STEP[1] : Install Docker

a) If the OS reside in virtualbox install Docker  else proceed to STEP [2].

b) Older versions of Docker were called docker or docker-engine. 
   If these are installed, uninstall them, along with associated dependencies:

	$ sudo apt-get remove docker docker-engine docker.io containerd runc

c) Update ubuntu

	$ sudo apt-get update

d) Install packages to allow apt to use a repository over HTTPS:

	$ sudo apt-get install \apt-transport-https \ca-certificates \	curl \gnupg-agent \software-properties-common

e) Add Docker’s official GPG key:

	$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | 	sudo apt-key add -
--------------------------------------------------------------------------------------------------------------------------------------------------
## Note : If OS is running in VirtualBox some may show curl need to be installed, in such scenario install curl:

	$ sudo apt install curl
	
	$ sudo curl version   
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

	$ sudo apt-key fingerprint 0EBFCD88
   
## Output: 
	
	pub   rsa4096 2017-02-22 [SCEA]
      9DC8 5822 9FC7 DD38 854A  E2D8 8D81 803C 0EBF CD88
	uid           [ unknown] Docker Release (CE deb) <docker@docker.com>
	sub   rsa4096 2017-02-22 [S]

f) Use the following command to set up the stable repository:	
	
	$ sudo add-apt-repository \"deb [arch=amd64] 	https://download.docker.com/linux/ubuntu \$(lsb_release -cs) \stable"

g) Update ubuntu

	$ sudo apt-get update

f) Install the latest version of Docker Engine - Community and containerd

	$ sudo apt-get install docker-ce docker-ce-cli containerd.io

h) Install latest version by this command

	$ sudo apt install docker-ce docker-ce-cli containerd.io

i) Verify that Docker Engine-Community is installed correctly                          

	$ sudo docker run hello-world

This command downloads a test image and runs it in a container. When the container runs, it prints an informational message and exits.

		   Docker Installed Successfully


## STEP[2] : Install Minikube and kubernetes

a) To check if virtualization is supported on Linux, run the following command 

	$   grep -E --color 'vmx|svm' /proc/cpuinfo
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Note: The output should be non empty
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

b) Install Minikube via direct download

	$ sudo -Lo minikube https://storage.googleapis.com minikube/releases/latest/minikube-linux-amd64 \&& chmod +x minikube 

c) add the Minikube executable to your path:

	$ sudo mkdir -p /usr/local/bin/
	$  sudo install minikube /usr/local/bin/

e) Confirm Installation:

	$ sudo minikube start –vm-driver=<driver_name>
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Note: In virtual Box

	$ sudo minikube start –vm-driver=none
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

Warning: The minikube is incomplete till the installation of kubernetes.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

f) Download the Kubernetes latest release with the command:

	$ sudo curl -LO https://storage.googleapis.com/kubernetes-release/release `curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
 
	$ curl -LO  https://storage.googleapis.com/kubernetes-release/  release/v1.17.0/bin/linux/amd64/kubectl  
		
			/|\
			 |
			 |
	[To download specific version]

g) Make the kubectl binary executable:

	$ sudo chmod +x ./kubectl

f) Move the binary in to your PATH.

	$  sudo mv ./kubectl /usr/local/bin/kubectl

h) Start Minikube 

	$ sudo minikube start
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Expected Result:

😄  minikube v1.6.2 on Ubuntu 18.04 (vbox/amd64)
✨  Selecting 'none' driver from existing profile (alternates: [])
💡  Tip: Use 'minikube start -p <name>' to create a new cluster, or 'minikube delete' to delete this one.
🔄  Starting existing none VM for "minikube" ...
⌛  Waiting for the host to be provisioned ...
🐳  Preparing Kubernetes v1.17.0 on Docker '19.03.5' ...
    ▪ kubelet.resolv-conf=/run/systemd/resolve/resolv.conf
🚀  Launching Kubernetes ... 
🤹  Configuring local host environment ...

⚠️  The 'none' driver provides limited isolation and may reduce system security and reliability.
⚠️  For more information, see:
👉  https://minikube.sigs.k8s.io/docs/reference/drivers/none/

⚠️  kubectl and minikube configuration will be stored in /home/manvantara
⚠️  To use kubectl or minikube commands as your own user, you may need to relocate them. For example, to overwrite your own settings, run:

    ▪ sudo mv /home/manvantara/.kube /home/manvantara/.minikube $HOME
    ▪ sudo chown -R $USER $HOME/.kube $HOME/.minikube

💡  This can also be done automatically by setting the env var CHANGE_MINIKUBE_NONE_USER=true
🏄  Done! kubectl is now configured to use "minikube"
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

i) Check minikube status and kubernetes version

	$ sudo minikube status
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Expected Output:

host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

	$ sudo kubectl version


	
## Good to work on K8 


