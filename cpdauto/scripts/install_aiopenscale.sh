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
cp ./templates/cpd/wos-sub.yaml wos-sub.yaml
cp ./templates/cpd/wos-cr.yaml wos-cr.yaml

mkdir -p ./logs
touch ./logs/install_wos.log
echo '' > ./logs/install_wos.log

# Create Watson OpenScale catalog source 

echo '*** executing **** create Watson OpenScale catalog source' >> ./logs/install_wos.log


cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory ibmWatsonOpenscaleOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m

# Install Watson OpenScale operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g wos-sub.yaml

echo '*** executing **** oc apply -f wos-sub.yaml' >> ./logs/install_wos.log
result=$(oc apply -f wos-sub.yaml)
echo $result  >> ./logs/install_wos.log
sleep 1m


# Checking if the Watson OpenScale operator pods are ready and running. 

./pod-status-check.sh ibm-cpd-wos ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create Watson OpenScale CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wos-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g wos-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g wos-cr.yaml


echo '*** executing **** oc apply -f wos-cr.yaml' >> ./logs/install_wos.log
result=$(oc apply -f wos-cr.yaml)
echo $result >> ./logs/install_wos.log

# check the Watson OpenScale cr status

./check-cr-status.sh WOService aiopenscale ${CPD_INSTANCE_NAMESPACE} wosStatus