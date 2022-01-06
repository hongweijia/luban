#!/bin/bash



OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
CPD_OPERATORS_NAMESPACE=$4
CPD_INSTANCE_NAMESPACE=$5
CPD_LICENSE=$6
STORAGE_TYPE=$7
STORAGE_CLASS=$8

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/wsl-sub.yaml wsl-sub.yaml
cp ./templates/cpd/wsl-cr.yaml wsl-cr.yaml

mkdir -p ./logs
touch ./logs/install_wsl.log
echo '' > ./logs/install_wsl.log

# Create wsl catalog source 

echo '*** executing **** create WSL catalog source' >> ./logs/install_wsl.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory wslSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--registry ${PRIVATE_REGISTRY} --inputDir ${OFFLINEDIR} --recursive"


sleep 1m

# Install wsl operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g wsl-sub.yaml

echo '*** executing **** oc apply -f wsl-sub.yaml' >> ./logs/install_wsl.log
result=$(oc apply -f wsl-sub.yaml)
echo $result  >> ./logs/install_wsl.log
sleep 1m


# Checking if the wsl operator pods are ready and running. 

./pod-status-check.sh ibm-cpd-ws-operator ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create wsl CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wsl-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g wsl-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g wsl-cr.yaml
if [[ ${STORAGE_TYPE} == "nfs" ]]
then
  sed -i "/storageVendor/d" wsl-cr.yaml
fi
sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g wsl-cr.yaml

result=$(oc apply -f wsl-cr.yaml)
echo $result >> ./logs/install_wsl.log

# check the WSL cr status

./check-cr-status.sh ws ws-cr ${CPD_INSTANCE_NAMESPACE} wsStatus