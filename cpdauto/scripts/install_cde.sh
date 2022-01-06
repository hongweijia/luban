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
cp ./templates/cpd/cde-sub.yaml cde-sub.yaml
cp ./templates/cpd/cde-cr.yaml cde-cr.yaml

mkdir -p ./logs
touch ./logs/install_cde.log
echo '' > ./logs/install_cde.log

# Create Cognos Dashboard catalog source 

echo '*** executing **** create Cognos Dashboard catalog source' >> ./logs/install_cde.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory cdeOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m

# Install Cognos Dashboard operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cde-sub.yaml

echo '*** executing **** oc apply -f cde-sub.yaml' >> ./logs/install_cde.log
result=$(oc apply -f cde-sub.yaml)
echo $result  >> ./logs/install_cde.log
sleep 1m


# Checking if the Cognos Dashboard operator pods are ready and running. 

./pod-status-check.sh ibm-cde-operator ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create Cognos Dashboard CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g cde-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g cde-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g cde-cr.yaml
#if [[ ${STORAGE_TYPE} == "nfs" ]]
#then
#  sed -i "/storageVendor/d" cde-cr.yaml
#fi

result=$(oc apply -f cde-cr.yaml)
echo $result >> ./logs/install_cde.log

# check the Cognos Dashboard cr status

./check-cr-status.sh CdeProxyService cdeproxyservice-cr ${CPD_INSTANCE_NAMESPACE} cdeStatus