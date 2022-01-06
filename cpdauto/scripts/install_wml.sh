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
cp ./templates/cpd/wml-sub.yaml wml-sub.yaml
cp ./templates/cpd/wml-cr.yaml wml-cr.yaml

mkdir -p ./logs
touch ./logs/install_wml.log
echo '' > ./logs/install_wml.log

# Create wml catalog source 

echo '*** executing **** create WML catalog source' >> ./logs/install_wml.log


cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory wmlOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--registry ${PRIVATE_REGISTRY} --inputDir ${OFFLINEDIR} --recursive"


sleep 1m

# Install wml operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g wml-sub.yaml

echo '*** executing **** oc apply -f wml-sub.yaml' >> ./logs/install_wml.log
result=$(oc apply -f wml-sub.yaml)
echo $result  >> ./logs/install_wml.log
sleep 1m


# Checking if the wml operator pods are ready and running. 

./pod-status-check.sh ibm-cpd-wml-operator ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create wml CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wml-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g wml-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g wml-cr.yaml
if [[ ${STORAGE_TYPE} == "nfs" ]]
then
  STORAGE_TYPE="\"\""
fi
sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g wml-cr.yaml

echo '*** executing **** oc apply -f wml-cr.yaml' >> ./logs/install_wml.log
result=$(oc apply -f wml-cr.yaml)
echo $result >> ./logs/install_wml.log

# check the wml cr status

./check-cr-status.sh WmlBase wml-cr ${CPD_INSTANCE_NAMESPACE} wmlStatus