This is the introduction about how to use Cloud Pak for Data Installation Accelerator to accelerate the deployment of Cloud Pak for Data in in various scenarios.

# Values
* Avoid human errors
* Reduce the time and efforts
* Improve the deployment experience 

# Scenarios
* Scenarios supported </br>
Install CPD 3.5 with the Portworx, OCS or NFS.
# Prequisites
The following prequisites have been met.
* OpenShift 4.5/4.6 cluster with a cluster admin user is available
* OpenShift image registry has been set up
* The Portworx, OCS or NFS storage class is ready
* CPD installer and installation files downloaded
https://www.ibm.com/docs/en/cloud-paks/cp-data/3.5.0?topic=tasks-obtaining-installation-files
* python3 and pip have been installed
* Precheck has been done and passed successfully

# Key artifacts
* Installation configure file
* Templates for changing node settings
* Python scripts

# Step by step guide
The following procedures are supposed to run in the Bastion node.

## 1.Precheck
https://github.com/IBM-ICP4D/Install_Precheck_CPD_v3

## 2.Install tools and libs
* yum install -y python3
* ln -s /usr/bin/python3 /usr/bin/python
* ln -s /usr/bin/pip3 /usr/bin/pip
* pip install ./cpdauto/packages/configparser-4.0.2-py2.py3-none-any.whl
* cp ./cpdauto/packages/jq-linux64 /usr/bin/jq

[Installing Python and packages on an Offline Machine: A Comprehensive Guide](https://stackoverflow.com/questions/56853876/installing-python-2-7-16-and-packages-offline-concerns-with-dependencies)

## 3. Create the log directory
mkdir -p /ibm/logs

## 4.Cluster settings
### Timeout settings for OpenShift image registry
`oc annotate route default-route default-route --overwrite haproxy.router.openshift.io/timeout=10m -n openshift-image-registry`

### Load balancer timeout settings
As the load balancer have several options and sometimes it's not available to operate them directly, so the manual work is still needed.
[Load balancer timeout settings](https://www.ibm.com/docs/en/cloud-paks/cp-data/3.5.0?topic=tasks-changing-required-node-settings#node-settings__lb-proxyhttps://www.ibm.com/docs/en/cloud-paks/cp-data/3.5.0?topic=tasks-changing-required-node-settings#node-settings__lb-proxy)

### Prepare the Node setting templates
**CRI-O container settings**<br/>
On Red Hat OpenShift version 4.5/4.6, Machine Config Pools manage your cluster of nodes and their corresponding Machine Configs (machineconfig). To change a setting in the crio.conf file, you can create a new machineconfig containing only the crio.conf file.

copy the crio.conf settings from a worker node by running the scp command from the worker node. Run this command from a terminal within the cluster network to make sure that you do not override an existing manual configuration. <br/>
`scp core@$(oc get nodes | grep worker | head -1 | awk '{print $1}'):/etc/crio/crio.conf /tmp/crio.conf`

Verify that /tmp/crio.conf looks like the template https://github.com/IBM/luban/blob/main/cpdauto/scripts/templates/cpd/crio.conf. If not, edit or add the following entries about **default_ulimits** and **pids_limit** in the **[crio.runtime]** section of the /tmp/crio.conf file.

`sed -i 's/pids_limit.*/pids_limit = 12290\ndefault_ulimits = [\n\ \ \ \ "nofile=66560:66560"\n]/g' /tmp/crio.conf`

After the verification passed, move the `/tmp/crio.conf` file to the folder `**cpdauto/scripts/templates/cpd/**`.

## 5.Configure your installation
Please refer to the template cpd_install.conf and update accordingly.
https://github.com/IBM/luban/blob/main/cpdauto/cpd_install.conf

## 6.Launch the installation
`cd ./cpdauto/scripts`<br/>
`chmod +x ./bootstrap.sh`<br/>
`nohup ./bootstrap.sh &`

## 7.Monitor the installation
### Overview
Check the log file overall_log_file that you specified in cpd_install.conf. <br/>
Or run the following command:
`watch -n 10 "tail -n 10 nohup.out"`
### Details
There will be logs corresponding to the push, apply and install commands for each assembly.
`ls /ibm/logs/`
Check the log for details.

## 8.Validate the installation status
### Check the installed assembly's status
`cpd-linux status -n yournamespace`

## 9.Troubleshooting
If the auto installation failed, you can do the troubleshooting as follows.
### 1)Check the logs as mentioned in Step 7
### 2)Check the logs of cpd-install-operator
`oc logs $(oc get po | grep cpd-install-operator | awk '{print }')`
### 3)Check if some pods failed to start up during the installation
`oc get po --no-headers --all-namespaces -o wide| grep -Ev '([[:digit:]])/\1.*R' | grep -v 'Completed'`
### 4)Switch to the manual installation
If the auto installation keeps failing, then there maybe something wrong with the environment and it's better handle the installation manually.










