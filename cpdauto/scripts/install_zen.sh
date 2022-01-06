#!/bin/bash


OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
BEDROCK_NAMESPACE=$4
CPD_OPERATORS_NAMESPACE=$5
CPD_INSTANCE_NAMESPACE=$6
CPD_LICENSE=$7
STORAGE_CLASS=$8
STORAGE_TYPE=$9

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/cpd-operator-group.yaml cpd-operator-group.yaml
cp ./templates/cpd/cpd-operator-sub.yaml cpd-operator-sub.yaml
cp ./templates/cpd/cpd-operators-namespace-scope-operator.yaml cpd-operators-namespace-scope-operator.yaml
cp ./templates/cpd/cpd-operators-namespace-scope.yaml cpd-operators-namespace-scope.yaml
cp ./templates/cpd/ibmcpd-cr.yaml ibmcpd-cr.yaml

mkdir -p ./logs
touch ./logs/install_cpd_platform.log
echo '' > ./logs/install_cpd_platform.log

# Create zen catalog source 

echo '*** executing **** create Cloud Pak for Data Platform (zen) catalog source' >> ./logs/install_cpd_platform.log

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory cpdPlatformOperator \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--registry ${PRIVATE_REGISTRY} --inputDir ${OFFLINEDIR} --recursive"


sleep 1m

# Create CPD Operators namespace
echo '*** executing **** create CPD Operators namespace ' >> ./logs/install_cpd_platform.log
oc new-project ${CPD_OPERATORS_NAMESPACE}
oc project ${CPD_OPERATORS_NAMESPACE}



# Create CPD operator group: 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operator-group.yaml

echo '*** executing **** oc apply -f cpd-operator-group.yaml' >> ./logs/install_cpd_platform.log


result=$(oc apply -f cpd-operator-group.yaml)
echo $result >> ./logs/install_cpd_platform.log
sleep 1m


sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operator-sub.yaml
echo '*** executing **** oc apply -f cpd-operator-sub.yaml' >> ./logs/install_cpd_platform.log
result=$(oc apply -f cpd-operator-sub.yaml)
echo $result >> ./logs/install_cpd_platform.log
sleep 60

######v2.0.5 has to be changed for new release!!!!#########
while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} cpd-operator -o jsonpath='{.status.installedCSV} {"\n"}' | grep cpd-platform-operator.v2.0.5 >/dev/null 2>&1; then
  echo -e "\ncpd-platform-operator.v2.0.5 was successfully created." >> ./logs/install_cpd_platform.log
  break
fi
sleep 10
done
######v2.0.5 has to be changed for new release!!!!#########
while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} cpd-platform-operator.v2.0.5 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors" >> ./logs/install_cpd_platform.log
  break
fi
sleep 10
done
######v2.0.5 has to be changed for new release!!!!#########
while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="cpd-platform-operator.v2.0.5" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\ncpd-platform-operator.v2.0.5 is ready." >> ./logs/install_cpd_platform.log
  break
fi
sleep 10
done

while true; do
if oc get pods -n ${CPD_OPERATORS_NAMESPACE} | grep cpd-platform-operator-manager >/dev/null 2>&1; then
  echo -e "\ncpd-platform-operator-manager pods running" >> ./logs/install_cpd_platform.log
  break
fi
sleep 10
done


# Create zen namespace
echo '*** executing **** create CPD Instance namespace ' >> ./logs/install_cpd_platform.log
oc new-project ${CPD_INSTANCE_NAMESPACE}
oc project ${CPD_INSTANCE_NAMESPACE}

# Create NameScope Operator in CPD Operators namespace 
echo '*** executing **** Create NameScope Operator in CPD Operators namespace' >> ./logs/install_cpd_platform.log
sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operators-namespace-scope-operator.yaml
echo '*** executing **** oc apply -f cpd-operators-namespace-scope-operator.yaml' >> ./logs/install_cpd_platform.log
result=$(oc apply -f cpd-operators-namespace-scope-operator.yaml)
echo $result >> ./logs/install_cpd_platform.log
sleep 5m

# Create NameScope in CPD Operators namespace 
echo '*** executing **** Create NameScope in CPD Operators namespace' >> ./logs/install_cpd_platform.log
sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operators-namespace-scope.yaml
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g cpd-operators-namespace-scope.yaml
echo '*** executing **** oc apply -f cpd-operators-namespace-scope.yaml' >> ./logs/install_cpd_platform.log
result=$(oc apply -f cpd-operators-namespace-scope.yaml)
echo $result >> ./logs/install_cpd_platform.log
sleep 30

echo '*** executing **** Patch NamespaceScope cpd-operators' >> ./logs/install_cpd_platform.log
oc patch NamespaceScope cpd-operators -n ${CPD_OPERATORS_NAMESPACE} --type=merge --patch='{"spec": {"csvInjector": {"enable": true} } }'

# Create lite CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g ibmcpd-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g ibmcpd-cr.yaml
sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g ibmcpd-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g ibmcpd-cr.yaml

if [[ ${STORAGE_TYPE} == "nfs" ]]
then
  sed -i "/storageVendor/d" ibmcpd-cr.yaml
else
  sed -i "/storageClass/d" ibmcpd-cr.yaml
fi

echo '*** executing **** oc create -f ibmcpd-cr.yaml' >> ./logs/install_cpd_platform.log
result=$(oc create -f ibmcpd-cr.yaml)
echo $result >> ./logs/install_cpd_platform.log

# check if the namespace scope operator pod is up and running.
./pod-status-check.sh ibm-namespace-scope-operator ${CPD_OPERATORS_NAMESPACE}

# check if the zen operator pod is up and running.

./pod-status-check.sh ibm-zen-operator ${BEDROCK_NAMESPACE}
./pod-status-check.sh ibm-cert-manager-operator ${BEDROCK_NAMESPACE}

./pod-status-check.sh cert-manager-cainjector ${BEDROCK_NAMESPACE}
./pod-status-check.sh cert-manager-controller ${BEDROCK_NAMESPACE}
./pod-status-check.sh cert-manager-webhook ${BEDROCK_NAMESPACE}

# check the lite cr status

./check-cr-status.sh ibmcpd ibmcpd-cr ${CPD_INSTANCE_NAMESPACE} controlPlaneStatus