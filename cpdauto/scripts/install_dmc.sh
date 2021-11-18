#!/bin/bash

#DMC 4.0.2

OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
BEDROCK_NAMESPACE=$4
CPD_OPERATORS_NAMESPACE=$5
CPD_INSTANCE_NAMESPACE=$6
CPD_LICENSE=$7

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/dmc-sub.yaml dmc-sub.yaml
cp ./templates/cpd/dmc-cr.yaml dmc-cr.yaml

mkdir -p ./logs
touch ./logs/install_dmc.log
echo '' > ./logs/install_dmc.log

# Create DMC catalog source 

echo '*** executing **** create DMC catalog source' >> ./logs/install_dmc.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory dmcOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m

# Install DMC operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g dmc-sub.yaml

echo '*** executing **** oc apply -f dmc-sub.yaml' >> ./logs/install_dmc.log
result=$(oc apply -f dmc-sub.yaml)
echo $result  >> ./logs/install_dmc.log
sleep 1m


# Checking if the DMC operator pods are ready and running. 

./pod-status-check.sh ibm-dmc-operator ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create DMC CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g dmc-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g dmc-cr.yaml
#sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g dmc-cr.yaml
#sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g dmc-cr.yaml
#if [[ ${STORAGE_TYPE} == "nfs" ]]
#then
##  sed -i "/storageVendor/d" dmc-cr.yaml
#else
#  sed -i "/storageClass/d" dmc-cr.yaml
#fi

############Check DMC operator status Start################
######ibm-databases-dmc.v1.0.2 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} ibm-dmc-operator-subscription -o jsonpath='{.status.installedCSV} {"\n"}' | grep ibm-databases-dmc.v1.0.2 >/dev/null 2>&1; then
  echo -e "\nibm-databases-dmc.v1.0.2 was successfully created." >> ./logs/install_dmc.log
  break
fi
sleep 10
done
######ibm-databases-dmc.v1.0.2 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} ibm-databases-dmc.v1.0.2 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_dmc.log
  break
fi
sleep 10
done
######ibm-databases-dmc.v1.0.2 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="ibm-databases-dmc.v1.0.2" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\nibm-databases-dmc.v1.0.2 is ready." >> ./logs/install_dmc.log
  break
fi
sleep 10
done
############Check DMC operator status End################

echo '*** executing **** oc apply -f dmc-cr.yaml' >> ./logs/install_dmc.log
result=$(oc apply -f dmc-cr.yaml)
echo $result >> ./logs/install_dmc.log

# check the DMC cr status

./check-cr-status.sh Dmcaddon dmc-addon ${CPD_INSTANCE_NAMESPACE} dmcAddonStatus
