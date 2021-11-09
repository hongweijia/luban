#!/bin/bash



OFFLINEDIR=$1
DB2AAS_CASE_PACKAGE_NAME=$2
DB2U_CASE_PACKAGE_NAME=$3

mkdir -p ./logs
touch ./logs/install_db2u.log
echo '' > ./logs/install_db2u.log

# Create Db2U catalog source 

echo '*** executing **** create Db2U catalog source' >> ./logs/install_db2u.log
#
yum install -y python2
unlink /usr/bin/python
ln -s /usr/bin/python2 /usr/bin/python
pip2 install pyyaml

cloudctl case launch \
--case ${OFFLINEDIR}/${DB2AAS_CASE_PACKAGE_NAME} \
--inventory db2aaserviceOperatorSetup \
--namespace openshift-marketplace \
--action install-catalog \
--args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m

cloudctl case launch \
  --case ${OFFLINEDIR}/${DB2U_CASE_PACKAGE_NAME} \
  --inventory db2uOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
    --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m

unlink /usr/bin/python
ln -s /usr/bin/python3 /usr/bin/python