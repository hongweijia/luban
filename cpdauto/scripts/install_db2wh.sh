#!/bin/bash

#Db2WH 4.0.2

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
cp ./templates/cpd/db2wh-sub.yaml db2wh-sub.yaml
cp ./templates/cpd/db2wh-cr.yaml db2wh-cr.yaml

mkdir -p ./logs
touch ./logs/install_db2wh.log
echo '' > ./logs/install_db2wh.log

#install python3 related libs
#yum install -y python3
#unlink /usr/bin/python
#ln -s /usr/bin/python3 /usr/bin/python
pip3 install pyyaml

# Create Db2WH catalog source 

echo '*** executing **** create Db2WH catalog source' >> ./logs/install_db2wh.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory db2whOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
    --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m


#edit the IBM Cloud Pak foundational services operand registry to point to the project where the Cloud Pak for Data operators are installed
oc -n ${BEDROCK_NAMESPACE} get operandRegistry common-service -o yaml > operandRegistry.yaml

tr '\n' '@' < operandRegistry.yaml > operandRegistry_tmp.yaml
sed -i -E "s/(namespace: .+)${BEDROCK_NAMESPACE}@(.+packageName: db2u-operator@)/\1${CPD_OPERATORS_NAMESPACE}@\2/" operandRegistry_tmp.yaml
tr '@' '\n' < operandRegistry_tmp.yaml > operandRegistry_replaced.yaml

echo "*** executing **** oc -n ${BEDROCK_NAMESPACE} apply -f operandRegistry_replaced.yaml" >> ./logs/install_db2wh.log
result=$(oc -n ${BEDROCK_NAMESPACE} apply -f operandRegistry_replaced.yaml)
echo $result  >> ./logs/install_db2wh.log
sleep 1m


# Install Db2WH operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g db2wh-sub.yaml

echo '*** executing **** oc apply -f db2wh-sub.yaml' >> ./logs/install_db2wh.log
result=$(oc apply -f db2wh-sub.yaml)
echo $result  >> ./logs/install_db2wh.log
sleep 1m


# Checking if the Db2WH operator pods are ready and running. 

./pod-status-check.sh ibm-db2wh-cp4d-operator ${CPD_OPERATORS_NAMESPACE}


############Check Db2WH operator status Start################
######ibm-db2wh-cp4d-operator.v1.0.3 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} ibm-db2wh-cp4d-operator-catalog-subscription -o jsonpath='{.status.installedCSV} {"\n"}' | grep ibm-db2wh-cp4d-operator.v1.0.3 >/dev/null 2>&1; then
  echo -e "\nibm-db2wh-cp4d-operator.v1.0.3 was successfully created." >> ./logs/install_db2wh.log
  break
fi
sleep 10
done
######ibm-db2wh-cp4d-operator.v1.0.3 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} ibm-db2wh-cp4d-operator.v1.0.3 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_db2wh.log
  break
fi
sleep 10
done
######ibm-db2wh-cp4d-operator.v1.0.3 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="ibm-db2wh-cp4d-operator.v1.0.3" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\nibm-db2wh-cp4d-operator.v1.0.3 is ready." >> ./logs/install_db2wh.log
  break
fi
sleep 10
done
############Check Db2WH operator status End################

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

#Enable unsafe sysctls on Red Hat® OpenShift - This has been done by the db2-kubelet-config-mc.yaml
# Create Db2WH CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g db2wh-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g db2wh-cr.yaml
sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g db2wh-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g db2wh-cr.yaml
if [[ ${STORAGE_TYPE} == "nfs" ]]
then
  sed -i "/storageVendor/d" db2wh-cr.yaml
else
  sed -i "/storageClass/d" db2wh-cr.yaml
fi

echo '*** executing **** oc apply -f db2wh-cr.yaml' >> ./logs/install_db2wh.log
result=$(oc apply -f db2wh-cr.yaml)
echo $result >> ./logs/install_db2wh.log


############Check Db2u operator status Start################
######v1.1.5 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} ibm-db2u-operator -o jsonpath='{.status.installedCSV} {"\n"}' | grep db2u-operator.v1.1.5 >/dev/null 2>&1; then
  echo -e "\ndb2u-operator.v1.1.5 was successfully created." >> ./logs/install_db2wh.log
  break
fi
sleep 10
done
######v1.1.5 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} db2u-operator.v1.1.5 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_db2wh.log
  break
fi
sleep 10
done
######v1.1.5 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="db2u-operator.v1.1.5" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\nibm-db2aaservice-cp4d-operator.v1.0.3 is ready." >> ./logs/install_db2wh.log
  break
fi
sleep 10
done

############Check Db2u operator status End##################


# check the Db2WH cr status

./check-cr-status.sh Db2whService db2wh-cr ${CPD_INSTANCE_NAMESPACE} db2whStatus
