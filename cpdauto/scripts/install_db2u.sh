#!/bin/bash



OFFLINEDIR=$1
DB2AAS_CASE_PACKAGE_NAME=$2
DB2U_CASE_PACKAGE_NAME=$3
CPD_OPERATORS_NAMESPACE=$4

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/db2u-sub.yaml db2u-sub.yaml

mkdir -p ./logs
touch ./logs/install_db2u.log
echo '' > ./logs/install_db2u.log

# Create Db2U catalog source 

echo '*** executing **** create Db2U catalog source' >> ./logs/install_db2u.log
#
#yum install -y python2
#unlink /usr/bin/python
#ln -s /usr/bin/python2 /usr/bin/python
#pip2 install pyyaml

yum install -y python3
pip3 install pyyaml

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

#unlink /usr/bin/python
#ln -s /usr/bin/python3 /usr/bin/python


# Install db2u operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g db2u-sub.yaml

echo '*** executing **** oc apply -f db2u-sub.yaml' >> ./logs/install_db2u.log
result=$(oc apply -f db2u-sub.yaml)
echo $result  >> ./logs/install_db2u.log
sleep 1m

############Check Db2u operator status Start################
######v1.1.8 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} ibm-db2u-operator -o jsonpath='{.status.installedCSV} {"\n"}' | grep db2u-operator.v1.1.8 >/dev/null 2>&1; then
  echo -e "\ndb2u-operator.v1.1.8 was successfully created." >> ./logs/install_db2u.log
  break
fi
sleep 10
done
######v1.1.8 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} db2u-operator.v1.1.8 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_db2u.log
  break
fi
sleep 10
done
######v1.1.8 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="db2u-operator.v1.1.8" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\nibm-db2aaservice-cp4d-operator.v1.0.3 is ready." >> ./logs/install_db2u.log
  break
fi
sleep 10
done

############Check Db2u operator status End##################