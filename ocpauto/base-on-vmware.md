# vmware_ocp_auto_install

The instruction in this repository is based on https://github.com/IBM-ICP4D/cloud-pak-ocp-4 which provides general guide on how to install Red Hat OpenShift 4.x(OCP) on VMWare or Bare Metal. But if you need to deploy multiple OCP environments without internet access, manually preparing air gapped registry and bastion node every time is tedious, time-consuming and error-prone. This instruction targets to resolve the problem, it provides best practice on:
* How to build 2in1 OVA template which includes air gapped registry and bastion node
* How to deploy OCP quickly on VMware leveraging above 2in1 OVA template

## Conditions and assumptions 
* VMware vCenter Server based (tested on VCSA 6.7 and ESXi 6.7).
* Air gapped registry, bastion node and NFS server are integrated into a 2in1 OVA template (RHEL8.1+)
* "Air gapped registry" and "bastion" mentioned below are both referring to the 2in1 VM deployed from the OVA template.
    * Air gapped registry hosts the OCP clients, installer, dependencies, etc. used for the OCP installation. Please note that the OCP image registry is not hosted here.
    * Bastion is the node used for load balancing, NFS sharing, DHCP, internal DNS and OCP cluster deploying.
* When preparing the air gapped registry & bastion node, it is not fully air gapped actually because you need to download packages and mirror the installation registry. It can be fully air gapped after the preparation completes, or is imported from the 2in1 OVA template.

## Prerequisites
* FQDN and DNS records for the cluster and OCP nodes are ready, including bastion, bootstrap, master, and worker nodes. If you need to access the nodes from outside the cluster, please register DNS records into an external DNS server.
    * The FQDN format should be ```<host_name>.<cluster_name>.<domain_name>```, while the VM name displayed in vCenter Server will be ```<cluster_name>-<host_name>```, but the VM name does not impact DNS resolving.
        eg. If your domain_name is ```cdl.ibm.com``` and cluster_name is ```ocp46```, the FQDN and DNS record for a master node will be ```master01.ocp46.cdl.ibm.com```, and the VM name will be ```ocp46-master01```.
    * Besides the bastion, bootstrap, master, and worker nodes, please also register the following records into DNS, with the same IP address as the bastion node:
        ```
        api.<cluster_name>.<domain_name>    <bastion IP>
        api-int.<cluster_name>.<domain_name>    <bastion IP>
        *.apps.<cluster_name>.<domain_name>    <bastion IP>
        ```
* A valid vCenter Server admin account which is able to import OVA templates, access datacenter/cluster/resource pool/datastore/network, and deploy VMs from templates. For simplicity, you can use a global administrator.
* The bastion node should be in the same vlan with bootstrap, master, and worker nodes, so that the nodes are able to get IP addresses from the DHCP server running on the bastion node. Typically you can put them into "VM Network", but please avoid multiple DHCP servers working in the same time when deploying OCP nodes.
* Get valid pull secret from Red Hat.
    A pull secret is needed to download the OpenShift assets from the Red Hat registry. You can download your pull secret from:
    https://cloud.redhat.com/openshift/install/vsphere/user-provisioned

## Prepare the air gapped registry & bastion node
If you start from scratch and need to create a 2in1 air gapped registry & bastion node, or 2 separate nodes, please read through this section.  
If you have already got an existing air gapped registry, please create a new VM used as the bastion node, and on it perform tasks described in [Prepare the bastion node](#Prepare-the-bastion-node).  
Or if you have got the 2in1 OVA template of the air gapped registry & bastion node, please skip to [Deploy an OCP cluster from the bastion node](#Deploy-an-OCP-cluster-from-the-bastion-node).

### Prepare the air gapped registry
1. Get ready a VM running RHEL8.1+, register the system to Red Hat, or configure your own local yum repos.
1. Disable firewalld service.
    ```
    # systemctl stop firewalld && systemctl disable firewalld
    ```
1. Set SELinux to permissive, or disable it.
    ```
    # setenforce 0
    # vi /etc/selinux/config
    ---
    SELINUX=permissive
    ```
1. Install required packages.
    ```
    # yum install -y wget podman httpd-tools jq nginx
    ```
1. If not registered in a DNS server, please add the following entry into ```/etc/hosts```:
    ```
    <ip address> <FQDN of this server> download.<domain_name> registry.<domain_name>
    ---
    eg. 9.1.1.2 bastion.cdl.ibm.com download.cdl.ibm.com registry.cdl.ibm.com
    ```
1. Set environment variables. You can also save them into a ```.sh``` script and source it, eg. ```# . env_vars.sh```.
    ```
    #!/bin/bash
    export REGISTRY_SERVER=registry.<domain_name>
    export REGISTRY_PORT=5000
    export LOCAL_REGISTRY="${REGISTRY_SERVER}:${REGISTRY_PORT}"
    export EMAIL="<your email address>"
    export REGISTRY_USER="admin"
    export REGISTRY_PASSWORD="Passw0rd"
    
    export OCP_RELEASE="4.6.18"
    export RHCOS_RELEASE="4.6.8"
    export LOCAL_REPOSITORY='ocp4/openshift4' 
    export PRODUCT_REPO='openshift-release-dev' 
    export LOCAL_SECRET_JSON='/ocp4_downloads/ocp4_install/ocp_pullsecret.json' 
    export RELEASE_NAME="ocp-release"
    
    # if get x509 error when mirroring registry, export the following
    export GODEBUG="x509ignoreCN=0"
    ```
1. Create directories for offline files.
    ```
    # mkdir -p /ocp4_downloads/{clients,dependencies,ocp4_install,ign}
    # mkdir -p /ocp4_downloads/registry/{auth,certs,data,images}
    ```
1. Download installation files and the RHCOS template.
    ```
    # cd /ocp4_downloads/clients
    # wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.6/openshift-client-linux.tar.gz
    # wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.6/openshift-install-linux.tar.gz

    # cd /ocp4_downloads/dependencies
    # wget https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/4.6/latest/rhcos-${RHCOS_RELEASE}-x86_64-vmware.x86_64.ova
    ```
1. Install OpenShift client.
    ```
    # tar xvzf /ocp4_downloads/clients/openshift-client-linux.tar.gz -C /usr/local/bin
    ```
1. Generate certificate and registry password.
    ```
    # cd /ocp4_downloads/registry/certs/
    # openssl req -newkey rsa:4096 -nodes -sha256 -keyout registry.key \
        -x509 -days 365 -out registry.crt \
        -subj "/C=US/ST=/L=/O=/CN=$REGISTRY_SERVER"

    # htpasswd -bBc /ocp4_downloads/registry/auth/htpasswd $REGISTRY_USER $REGISTRY_PASSWORD
    ```
1. Download registry and NFS provisioner.
    ```
    # podman pull docker.io/library/registry:2
    # podman save -o /ocp4_downloads/registry/images/registry-2.tar docker.io/library/registry:2

    # podman pull quay.io/external_storage/nfs-client-provisioner:latest
    # podman save -o /ocp4_downloads/registry/images/nfs-client-provisioner.tar quay.io/external_storage/nfs-client-provisioner:latest
    ```
1. Create the registry pod.
    ```
    podman run --name mirror-registry --publish $REGISTRY_PORT:5000 \
        --detach \
        --volume /ocp4_downloads/registry/data:/var/lib/registry:z \
        --volume /ocp4_downloads/registry/auth:/auth:z \
        --volume /ocp4_downloads/registry/certs:/certs:z \
        --env "REGISTRY_AUTH=htpasswd" \
        --env "REGISTRY_AUTH_HTPASSWD_REALM=Registry Realm" \
        --env REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
        --env REGISTRY_HTTP_TLS_CERTIFICATE=/certs/registry.crt \
        --env REGISTRY_HTTP_TLS_KEY=/certs/registry.key \
        docker.io/library/registry:2
    ```
1. Add the certificate to trusted store.
    ```
    # /usr/bin/cp -f /ocp4_downloads/registry/certs/registry.crt /etc/pki/ca-trust/source/anchors/
    # update-ca-trust
    ```
1. Check if the registry can be accessed.
    ```
    # curl -u $REGISTRY_USER:$REGISTRY_PASSWORD https://${LOCAL_REGISTRY}/v2/_catalog
    ---
    The output is expected to be:
        {"repositories":[]}
    ```
1. Copy your Red Hat pull secret into ```/tmp/ocp_pullsecret.json```.
1. Generate air gapped pull secret which is used for air gapped OCP installation.
    ```
    # AUTH=$(echo -n "$REGISTRY_USER:$REGISTRY_PASSWORD" | base64 -w0)
    # CUST_REG='{"%s": {"auth":"%s", "email":"%s"}}\n'
    # printf "$CUST_REG" "$LOCAL_REGISTRY" "$AUTH" "$EMAIL" > /tmp/local_reg.json
    # jq --argjson authinfo "$(</tmp/local_reg.json)" '.auths += $authinfo' /tmp/ocp_pullsecret.json > /ocp4_downloads/ocp4_install/ocp_pullsecret.json
    ```
1. Mirror the registry to local.
    ```
    # oc adm -a ${LOCAL_SECRET_JSON} release mirror \
        --from=quay.io/${PRODUCT_REPO}/${RELEASE_NAME}:${OCP_RELEASE}-x86_64 \
        --to=${LOCAL_REGISTRY}/${LOCAL_REPOSITORY} \
        --to-release-image=${LOCAL_REGISTRY}/${LOCAL_REPOSITORY}:${OCP_RELEASE}
    ```
1. Check if the registry can be accessed.
    ```
    # curl -u $REGISTRY_USER:$REGISTRY_PASSWORD https://${LOCAL_REGISTRY}/v2/_catalog
    ---
    The output is expected to be:
        {"repositories":["ocp4/openshift4"]}
    ```
1. Create systemd unit file and register the registry as a service.
    ```
    # podman generate systemd mirror-registry -n > /etc/systemd/system/container-mirror-registry.service
    # systemctl enable container-mirror-registry.service
    # systemctl daemon-reload
    ```
1. Configure Nginx HTTP server.
    ```
    # vi /etc/nginx/nginx.conf
    ---
        # Change the listening port
            server {
                listen       8080 default_server;
        ...
        # Add "/ocp4_downloads" location under "/"
            location /ocp4_downloads {
                autoindex on;
        ...
    ```
1. Create synbolic link to the downloads directory, and start the HTTP server.
    ```
    # ln -s /ocp4_downloads /usr/share/nginx/html/ocp4_downloads
    # systemctl restart nginx && systemctl enable nginx
    ```
1. Check if the HTTP service can be accessed.
    ```
    # curl -L -s http://${REGISTRY_SERVER}:8080/ocp4_downloads --list-only
    ---
    The output is expected to display folder names under /ocp4_downloads.
    ```

### Prepare the bastion node
Please note that if you are creating a 2in1 air gapped registry & bastion node, some tasks may have been completed or some packages may have been installed, so just skip them.
1. Get ready a VM running RHEL8.1+, register the system to Red Hat, or configure your own local yum repos.
1. Add an additional "bare" disk to this VM(typically /dev/sdb) used for NFS sharing. Please note that you do not need to partition and format it, while the installation script does this and will mount it for NFS sharing.
1. Disable firewalld service.
    ```
    # systemctl stop firewalld && systemctl disable firewalld
    ```
1. Install EPEL repo for yum.
    ```
    # yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    ```
1. Install required packages.
    ```
    # yum install -y ansible bind-utils buildah chrony dnsmasq git haproxy httpd-tools jq libvirt net-tools nfs-utils nginx podman python3 python3-netaddr python3-passlib python3-pip python3-policycoreutils python3-pyvmomi python3-requests screen sos syslinux-tftpboot wget yum-utils
    ```
1. Copy this script set into ```~/``` from github.ibm.com, or upload it as a zip file and extract it.
    ```
    # cd ~/
    # git clone https://github.com/IBM-ICP4D/cloud-pak-ocp-4.git
    ```
    It is assumed that the scripts are located in ```~/cloud-pak-ocp-4/```.

Then you can skip to [Deploy the RHCOS template from OVA](#Deploy-the-RHCOS-template-from-OVA) and continue the installation.  
Or, you can shutdown this VM and export it as a **"2in1 OVA/OVF template"**.


## Deploy an OCP cluster from the bastion node
### Re-configure air gapped registry & bastion node for your environment
1. Change root password accordingly.
1. Change the hostname, IP address, and update ```/etc/hosts``` records.
    ```
    # hostnamectl set-hostname <new FQDN>
    # vi /etc/sysconfig/network-scripts/ifcfg-ens192
    # vi /etc/hosts
    # reboot
    ```
1. Register the system to Red Hat or configure your own local yum repos.
1. Set environment variables.
    ```
    # vi ~/env_vars.sh
    ---
        export REGISTRY_SERVER=$(hostname -f)
        ...
        export EMAIL="<your email address>"
        export REGISTRY_USER="admin"
        export REGISTRY_PASSWORD="Passw0rd"
        ...
    ---
    # . env_vars.sh
    ```
1. Replace existing ```/tmp/ocp_pullsecret.json``` file with your own pull secret file.
1. Re-generate air gapped pull secret which is used for air gapped OCP installation.
    ```
    # AUTH=$(echo -n "$REGISTRY_USER:$REGISTRY_PASSWORD" | base64 -w0)
    # CUST_REG='{"%s": {"auth":"%s", "email":"%s"}}\n'
    # printf "$CUST_REG" "$LOCAL_REGISTRY" "$AUTH" "$EMAIL" > /tmp/local_reg.json
    # jq --argjson authinfo "$(</tmp/local_reg.json)" '.auths += $authinfo' /tmp/ocp_pullsecret.json > /ocp4_downloads/ocp4_install/ocp_pullsecret.json
    ```
1. Re-create certificate and registry password.
    ```
    # cd /ocp4_downloads/registry/certs/
    # rm registry.key
    # rm registry.crt

    # openssl req -newkey rsa:4096 -nodes -sha256 -keyout registry.key \
        -x509 -days 365 -out registry.crt \
        -subj "/C=US/ST=/L=/O=/CN=$REGISTRY_SERVER"

    # htpasswd -bBc /ocp4_downloads/registry/auth/htpasswd $REGISTRY_USER $REGISTRY_PASSWORD
    ```
1. Add the certificate to trusted store.
    ```
    # /usr/bin/cp -f /ocp4_downloads/registry/certs/registry.crt /etc/pki/ca-trust/source/anchors/
    # update-ca-trust
    ```
1. Re-create the registry pod.
    ```
    # systemctl stop container-mirror-registry.service
    # podman rm mirror-registry

    # podman load -i /ocp4_downloads/registry/images/registry-2.tar
    # podman run --name mirror-registry --publish $REGISTRY_PORT:5000 \
        --detach \
        --volume /ocp4_downloads/registry/data:/var/lib/registry:z \
        --volume /ocp4_downloads/registry/auth:/auth:z \
        --volume /ocp4_downloads/registry/certs:/certs:z \
        --env "REGISTRY_AUTH=htpasswd" \
        --env "REGISTRY_AUTH_HTPASSWD_REALM=Registry Realm" \
        --env REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
        --env REGISTRY_HTTP_TLS_CERTIFICATE=/certs/registry.crt \
        --env REGISTRY_HTTP_TLS_KEY=/certs/registry.key \
        docker.io/library/registry:2
    ```
1. Check if the registry can be accessed.
    ```
    # curl -u $REGISTRY_USER:$REGISTRY_PASSWORD https://${LOCAL_REGISTRY}/v2/_catalog
    ---
    The output is expected to be:
        {"repositories":["ocp4/openshift4"]}
    ```
1. Re-create systemd unit file and register the registry service.
    ```
    # podman generate systemd mirror-registry -n > /etc/systemd/system/container-mirror-registry.service
    # systemctl enable container-mirror-registry.service
    # systemctl daemon-reload
    # systemctl restart container-mirror-registry.service
    ```
1. (Optional) Change Nginx configurations and restart the service accordingly. Typically this step is not required.


## Deploy the RHCOS template from OVA
* From the client where you manage the vCenter Server, download the ova file from the air gapped registry.
    ```
    http://<airgapped-registry>:8080/ocp4_downloads/dependencies/<rhcos_name>.ova
    ```
* Deploy the RHCOS template
    * Deploy the VM from OVA
    ```
    place holder
    ```
    * (Optional) Enable CPU hardware virtualization
    ```
    place holder
    ```
    * Convert the VM to template
    ```
    place holder
    ```


## Install OCP cluster from bastion node
### Start OCP installation
When the air gapped registry & bastion node is ready, you can start deploying your OCP cluster from the bastion node.
1. Logon as "root" and go to the script location.
    ```
    # cd ~/cloud-pak-ocp-4 && ls
    ---
    ansible.cfg  inventory   README.md     vm_delete.sh
    doc          playbooks   TSD           vm_power_on.sh
    images       prepare.sh  vm_create.sh  vm_update_vapp.sh
    ```
1. Prepare the air gapped inventory file. Please read through the instructions in the inventory file and make changes according to your own environment.
    ```
    # cd inventory/
    # cp vmware-airgapped-example.inv airgapped.inv
    # vi airgapped.inv
    ```
    Please node that:
    * openshift_release="4.6"
    * rhcos_installation_method=ova  # will deploy nodes from RHCOS template.
    * http_server_port=8080  # set in the Nginx configurations.
    * If using DHCP, configure a proper IP range to avoid overlapping.
    * Leave MAC addresses as-is and they will be updated by the VM creation script.
    * Modify others according to your environment.
1. Create VMs for bootstrap, master, and worker nodes in the vCenter Server. 
    * (Optional) Set ```vc_user``` and ```vc_password``` as environment variables used for logging on your vCenter Server, otherwise you will be prompted to provide them manually when the srcipt starts.
        ```
        export vc_user=<vcenter username>
        export vc_password=<vcenter password>
        ```
    * Run VM creaton script.
        ```
        # cd ~/cloud-pak-ocp-4/
        # ./vm_create.sh -i inventory/airgapped.inv [-vvv]
        ```
1. Prepare for the OCP installation.
    * Download the air gapped pull secret.
        ```
        # wget http://${REGISTRY_SERVER}:8080/ocp4_downloads/ocp4_install/ocp_pullsecret.json -O /tmp/ocp_pullsecret.json
        # wget http://${REGISTRY_SERVER}:8080/ocp4_downloads/registry/certs/registry.crt -O /tmp/registry.crt
        ```
    * (Optional) Set ```root_password``` and ```ocp_admin_password``` as environment variables used for configuring bastion node SSH password-less logon and creating OCP user "admin".
        ```
        # export root_password=<root password of bastion(and NFS) server>
        # export ocp_admin_password=<ocp password for the 'admin' user>
        ```
    * Run the preparation script.
        ```
        # ./prepare.sh -i inventory/airgapped.inv [-vvv]
        ```
1. Update vApp options for bootstrap, master, and worker VMs.
    ```
    # ./vm_update_vapp.sh -i inventory/airgapped.inv [-vvv]
    ```
    This script copies bootstrap.ign file into the Nginx server and prepares ```.ign``` files, then update the vApp options for VMs.
    VMs will be initialized with these vApp options and apply the ```.ign``` configurations.
1. Start VMs and bootstrapping the OCP cluster.
    ```
    # ./vm_power_on.sh -i inventory/airgapped.inv [-vvv]
    ```
1. Wait for the bootstrapping to complete.
    ```
    # /ocp_install/scripts/wait_boostrap.sh [--log-level=debug]
    ```
    It typically takes 10-30 minutes.
    After the bootstrapping completes, you can stop the bootstrap node.
    ```
    # /ocp_install/scripts/remove_bootstrap.sh
    ```
    (Optional) Then the bootstrap VM can be deleted from vCenter Server.
1. **[Must Do]** Wait for all nodes to be ready.
    ```
    # /ocp_install/scripts/wait_nodes_ready.sh
    ```
    This script approves CSRs first and then wait for all nodes to be ready.
1. Create OCP user "admin".
    ```
    # /ocp_install/scripts/create_admin_user.sh
    ---
    Please ignore the user admin not found warning.
    ```
1. Wait for the OCP installation to complete.
    ```
    # /ocp_install/scripts/wait_install.sh
    ```
    After completion, it will show the OCP console link and "kubeadmin" user credential.
1. Wait for cluster operators to be ready.
    ```
    # /ocp_install/scripts/wait_co_ready.sh
    ```
    Once complete, you can logon to the OCP cluster as below:
    ```
    # unset KUBECONFIG
    # API_URL=$(grep "api-int" /etc/dnsmasq.conf | sed 's#.*\(api.*\)/.*#\1#')
    # oc login -s ${API_URL}:6443 -u <admin> -p <password> --insecure-skip-tls-verify=true
    ```
1. Create NFS storage class.
    ```
    # /ocp_install/scripts/create_nfs_sc.sh
    # oc get sc
    # oc get po
    ```
1. Create image registry.
    ```
    # /ocp_install/scripts/create_registry_storage.sh
    ```
1. Run post-installation.
    ```
    # /ocp_install/scripts/post_install.sh
    ```
    This scripts by default does not delete "kubeadmin" user. If you want to delete it, run:
    ```
    # oc delete secrets kubeadmin -n kube-system
    ```
    Once again, wait for all cluster operators to be ready.
    ```
    # /ocp_install/scripts/wait_co_ready.sh
    ```
1. (Optional) Disable DHCP serve.
    ```
    # /ocp_install/scripts/disable_dhcp.sh
    ```
    This scripts removes DHCP sections from the dnsmasq configurations and restarts dnsmasq service.  
    **Be careful that: If the DHCP service is disabled, nodes will not be able to get IP addresses after reboot.**


### Important
After completing the OpenShift 4.x installation, ensure that you keep the cluster running for at least 24 hours. This is required to renew the temporary control plane certificates. If you shut down the cluster nodes before the control plane certificates are renewed and they expire while the cluster is down, you will not be able to access OpenShift.

### (Optional) Start over from VM creation
If you encounter some unknown issues(eg. mis-configuration of cluster_name and domain_name) and want to re-create the node VMs, read through this section and start over from the VM creation step.
* Remove VMs by running ```./vm_delete.sh -i inventory/airgapped.inv```.
    * This will delete the node VMs from vCenter Server;
    * and delete ocp_install directory, and the leases file of DHCP service from the bastion node;
    * and remove hostname entries from /etc/hosts file of bastion node.
* Start over from running ```vm_create.sh```, ```prepare.sh```, etc.

