This is the introduction about how to use Cloud Pak for Data Installation Accelerator to accelerate the deployment of Cloud Pak for Data 4.0.3 Air-gapped environment.

# Values
* Avoid human errors
* Reduce the time and efforts
* Improve the deployment experience 

# Scenarios
* Scenarios supported </br>
Install CPD 4.0.3 with the Portworx, OCS or NFS.

# Key artifacts
* Installation configure file
* Templates for changing node settings
* Python and shell scripts

# Prequisites
The following prequisites have been met.
* OpenShift 4.8 cluster with a cluster admin user is available
* Cloud Pak for Data Cases and images have been downloaded
* docker.io/library/registry:2.7 image prepared and the private image registry has been set up
* The Portworx, OCS or NFS storage class is ready
* #CLOUDCTL downloaded by wget https://github.com/IBM/cloud-pak-cli/releases/download/v3.12.0/cloudctl-linux-amd64.tar.gz
* Download the luban-cpd-403.zip from this git repository https://github.com/hongweijia/luban/tree/cpd-403

# Step by step guide
The following procedures are supposed to run in the Bastion node.

1.Install required tools and libraries
yum install openssl httpd-tools podman skopeo git jq tmux -y
tar -xf cloudctl-linux-amd64.tar.gz
cp cloudctl-linux-amd64 /usr/bin/cloudctl
 
tmux </br>

2.Set up private image registry </br>

#The OFFLINEDIR has to be changed accordingly </br>
export OFFLINEDIR=/data/offline/cpd </br>
#PRIVATE_REGISTRY_HOST  and port needs to be changed to the Bastion node IP/Hostname </br>
export PRIVATE_REGISTRY_HOST=xxx </br>
export PRIVATE_REGISTRY_PORT=5000 </br>
export PRIVATE_REGISTRY=$PRIVATE_REGISTRY_HOST:$PRIVATE_REGISTRY_PORT </br>
#The port has to be changed accordingly </br>
export PRIVATE_REGISTRY_USER=admin </br>
export PRIVATE_REGISTRY_PASSWORD=password </br>
export PRIVATE_REGISTRY_PATH=$OFFLINEDIR/imageregistry </br>
export CLOUDCTL_TRACE=true # for extra logging </br>

cloudctl case launch --case ${OFFLINEDIR}/ibm-cp-datacore-2.0.8.tgz --inventory cpdPlatformOperator --action init-registry --args "--registry ${PRIVATE_REGISTRY_HOST} --user ${PRIVATE_REGISTRY_USER} --pass ${PRIVATE_REGISTRY_PASSWORD} --dir ${OFFLINEDIR}/imageregistry" </br>

cloudctl case launch --case ${OFFLINEDIR}/ibm-cp-datacore-2.0.8.tgz --inventory cpdPlatformOperator --action start-registry --args "--port ${PRIVATE_REGISTRY_PORT} --dir ${OFFLINEDIR}/imageregistry --image docker.io/library/registry:2.7" </br>

3. Pre-check </br>

1)Image registry </br>
podman login --username $PRIVATE_REGISTRY_USER --password $PRIVATE_REGISTRY_PASSWORD $PRIVATE_REGISTRY --tls-verify=false </br>

curl -k -u ${PRIVATE_REGISTRY_USER}:${PRIVATE_REGISTRY_PASSWORD} https://${PRIVATE_REGISTRY}/v2/_catalog?n=6000 | jq . </br>

2)Check case names </br>
ls $OFFLINEDIR </br>

3)Check python </br>
ls /usr/bin/python </br>

Make sure  python 3 are installed.

4)Check OCP status
oc get co
oc get nodes
oc get mcp

4. Configure the installation accelerator

mkdir /ibm
cd /ibm

#Assume you placed the luban-cpd-403.zip to /ibm folder
unzip luban-cpd-403.zip
 
yum install python3 jq -y

ln -s /usr/bin/python3 /usr/bin/python

mkdir -p /ibm/logs

cd /ibm/luban/cpdauto/

#This step is important. 
Especially double confirm  the [ocp_cred] , [image_registry], storage_type and storage_class are changed accordingly

vi cpd_install.conf

5. Launch the auto installation with the installation accelerator
#Launch the installation
cd /ibm/luban/cpdauto/scripts
./bootstrap.sh

6.Post-config
The timeout settings for the ha-proxy load balancer

sed -i -e "/timeout client/s/ [0-9].*/ 5m/" /etc/haproxy/haproxy.cfg
sed -i -e "/timeout server/s/ [0-9].*/ 5m/" /etc/haproxy/haproxy.cfg
systemctl restart haproxy
systemctl status haproxy
cat /etc/haproxy/haproxy.cfg | grep timeout

7.Get the URL of the Cloud Pak for Data web client:
oc get ZenService lite-cr -o jsonpath="{.status.url}{'\n'}"
 
Get the initial password for the admin user:
oc extract secret/admin-user-details --keys=initial_admin_password --to=-
