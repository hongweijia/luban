#!/bin/bash

#WKC 4.0.2

OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
BEDROCK_NAMESPACE=$4
CPD_OPERATORS_NAMESPACE=$5
CPD_INSTANCE_NAMESPACE=$6
CPD_LICENSE=$7
STORAGE_TYPE=$8
STORAGE_CLASS=$9

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/wkc-sub.yaml wkc-sub.yaml
cp ./templates/cpd/wkc-iis-scc.yaml wkc-iis-scc.yaml
cp ./templates/cpd/wkc-cr.yaml wkc-cr.yaml

mkdir -p ./logs
touch ./logs/install_wkc.log
echo '' > ./logs/install_wkc.log

#install python3 related libs
#yum install -y python3
#unlink /usr/bin/python
#ln -s /usr/bin/python3 /usr/bin/python
pip3 install pyyaml

# Create wkc catalog source 

echo '*** executing **** create WKC catalog source' >> ./logs/install_wkc.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory wkcOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--inputDir ${OFFLINEDIR} --recursive"


sleep 1m


#edit the IBM Cloud Pak foundational services operand registry to point to the project where the Cloud Pak for Data operators are installed
oc -n ${BEDROCK_NAMESPACE} get operandRegistry common-service -o yaml > operandRegistry.yaml

tr '\n' '@' < operandRegistry.yaml > operandRegistry_tmp.yaml
sed -i -E "s/(namespace: .+)${BEDROCK_NAMESPACE}@(.+packageName: db2u-operator@)/\1${CPD_OPERATORS_NAMESPACE}@\2/" operandRegistry_tmp.yaml
tr '@' '\n' < operandRegistry_tmp.yaml > operandRegistry_replaced.yaml

echo "*** executing **** oc -n ${BEDROCK_NAMESPACE} apply -f operandRegistry_replaced.yaml" >> ./logs/install_wkc.log
result=$(oc -n ${BEDROCK_NAMESPACE} apply -f operandRegistry_replaced.yaml)
echo $result  >> ./logs/install_wkc.log
sleep 1m


# Install wkc operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g wkc-sub.yaml

echo '*** executing **** oc apply -f wkc-sub.yaml' >> ./logs/install_wkc.log
result=$(oc apply -f wkc-sub.yaml)
echo $result  >> ./logs/install_wkc.log
sleep 1m


# Checking if the wkc operator pods are ready and running. 

./pod-status-check.sh ibm-cpd-wkc-operator ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create customer SCC
oc delete scc wkc-iis-scc
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wkc-iis-scc.yaml
echo '*** executing **** oc apply -f wkc-iis-scc.yaml' >> ./logs/install_wkc.log
result=$(oc apply -f wkc-iis-scc.yaml)
echo $result  >> ./logs/install_wkc.log
sleep 1m

echo '*** Create the SCC cluster role for wkc-iis-scc **** ' >> ./logs/install_wkc.log
result=$(oc create clusterrole system:openshift:scc:wkc-iis-scc --verb=use --resource=scc --resource-name=wkc-iis-scc)
echo $result  >> ./logs/install_wkc.log

echo '*** Assign the wkc-iis-sa service account to the SCC cluster role **** ' >> ./logs/install_wkc.log
result=$(oc create rolebinding wkc-iis-scc-rb --clusterrole=system:openshift:scc:wkc-iis-scc --serviceaccount=${CPD_INSTANCE_NAMESPACE}:wkc-iis-sa)
echo $result  >> ./logs/install_wkc.log

echo '*** Confirm that the wkc-iis-sa service account can use the wkc-iis-scc SCC **** ' >> ./logs/install_wkc.log
result=$(oc adm policy who-can use scc wkc-iis-scc -n ${CPD_INSTANCE_NAMESPACE} | grep "wkc-iis-sa")
echo $result  >> ./logs/install_wkc.log

#Enable unsafe sysctls on Red Hat® OpenShift - This has been done by the db2-kubelet-config-mc.yaml
# Create wkc CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wkc-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g wkc-cr.yaml
sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g wkc-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g wkc-cr.yaml
if [[ ${STORAGE_TYPE} == "nfs" ]]
then
  sed -i "/storageVendor/d" wkc-cr.yaml
else
  sed -i "/storageClass/d" wkc-cr.yaml
fi

echo '*** executing **** oc apply -f wkc-cr.yaml' >> ./logs/install_wkc.log
result=$(oc apply -f wkc-cr.yaml)
echo $result >> ./logs/install_wkc.log

############Check WKC operator status Start################
######v1.0.3 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} ibm-cpd-wkc-operator-catalog-subscription -o jsonpath='{.status.installedCSV} {"\n"}' | grep ibm-cpd-wkc.v1.0.3 >/dev/null 2>&1; then
  echo -e "\nibm-cpd-wkc.v1.0.3 was successfully created." >> ./logs/install_wkc.log
  break
fi
sleep 10
done
######v1.0.3 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} ibm-cpd-wkc.v1.0.3 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_wkc.log
  break
fi
sleep 10
done
######v1.0.3 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="ibm-cpd-wkc.v1.0.3" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\nibm-cpd-wkc.v1.0.3 is ready." >> ./logs/install_wkc.log
  break
fi
sleep 10
done
############Check WKC operator status End################

# check the wkc cr status

./check-cr-status.sh wkc wkc-cr ${CPD_INSTANCE_NAMESPACE} wkcStatus

./check-cr-status.sh ccs ccs-cr ${CPD_INSTANCE_NAMESPACE} ccsStatus

./check-cr-status.sh DataRefinery datarefinery-sample ${CPD_INSTANCE_NAMESPACE} datarefineryStatus

./check-cr-status.sh Db2aaserviceService db2aaservice-cr ${CPD_INSTANCE_NAMESPACE} db2aaserviceStatus

# check the iis cr status
./check-cr-status.sh iis iis-cr ${CPD_INSTANCE_NAMESPACE} iisStatus

# check the ug cr status
./check-cr-status.sh ug ug-cr ${CPD_INSTANCE_NAMESPACE} ugStatus