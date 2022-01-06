#!/bin/bash



OFFLINEDIR=$1
CCS_CASE_PACKAGE_NAME=$2


mkdir -p ./logs
touch ./logs/install_ccs.log
echo '' > ./logs/install_ccs.log

# Create CCS catalog source 

echo '*** executing **** create CCS catalog source' >> ./logs/install_ccs.log
#

cloudctl case launch \
  --case ${OFFLINEDIR}/${CCS_CASE_PACKAGE_NAME} \
  --inventory ccsSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m
