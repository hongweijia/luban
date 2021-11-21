#!/bin/bash

#DV 1.7.2

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
cp ./templates/cpd/dv-sub.yaml dv-sub.yaml
cp ./templates/cpd/dv-cr.yaml dv-cr.yaml

mkdir -p ./logs
touch ./logs/install_dv.log
echo '' > ./logs/install_dv.log

# Create DV catalog source 

echo '*** executing **** create DV catalog source' >> ./logs/install_dv.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory dv \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m

# Install DV operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g dv-sub.yaml

echo '*** executing **** oc apply -f dv-sub.yaml' >> ./logs/install_dv.log
result=$(oc apply -f dv-sub.yaml)
echo $result  >> ./logs/install_dv.log
sleep 1m

############Check DV operator status Start################
######ibm-dv-operator.v1.7.2 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} ibm-dv-operator-catalog-subscription -o jsonpath='{.status.installedCSV} {"\n"}' | grep ibm-dv-operator.v1.7.2 >/dev/null 2>&1; then
  echo -e "\nibm-dv-operator.v1.7.2 was successfully created." >> ./logs/install_dv.log
  break
fi
sleep 10
done
######ibm-dv-operator.v1.7.2 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} ibm-dv-operator.v1.7.2 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_dv.log
  break
fi
sleep 10
done
######ibm-dv-operator.v1.7.2 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="ibm-dv-operator.v1.7.2" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\nibm-dv-operator.v1.7.2 is ready." >> ./logs/install_dv.log
  break
fi
sleep 10
done

# Checking if the DV operator pods are ready and running. 

./pod-status-check.sh ibm-dv-operator ${CPD_OPERATORS_NAMESPACE}
############Check DV operator status End################

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create DV CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g dv-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g dv-cr.yaml
#sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g dv-cr.yaml
#sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g dv-cr.yaml
#if [[ ${STORAGE_TYPE} == "nfs" ]]
#then
##  sed -i "/storageVendor/d" dv-cr.yaml
#else
#  sed -i "/storageClass/d" dv-cr.yaml
#fi


echo '*** executing **** oc apply -f dv-cr.yaml' >> ./logs/install_dv.log
result=$(oc apply -f dv-cr.yaml)
echo $result >> ./logs/install_dv.log

# check the DV cr status

./check-cr-status.sh DvService dv-service ${CPD_INSTANCE_NAMESPACE} reconcileStatus
