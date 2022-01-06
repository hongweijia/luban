#!/bin/bash

OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
BEDROCK_NAMESPACE=$4

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/bedrock-operator-group.yaml bedrock-operator-group.yaml
cp ./templates/cpd/bedrock-sub.yaml bedrock-sub.yaml

mkdir -p ./logs
touch ./logs/install_bedrock.log
echo '' > ./logs/install_bedrock.log

# # create bedrock catalog source 

echo '*** executing **** create bedrock catalog source' >> ./logs/install_bedrock.log


cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory ibmCommonServiceOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--registry ${PRIVATE_REGISTRY} --inputDir ${OFFLINEDIR} --recursive"


sleep 1m


# Creating the ibm-common-services namespace: 

oc new-project ${BEDROCK_NAMESPACE}
oc project ${BEDROCK_NAMESPACE}

# Create bedrock operator group: 

sed -i -e s#BEDROCK_NAMESPACE#${BEDROCK_NAMESPACE}#g bedrock-operator-group.yaml

echo '*** executing **** oc apply -f bedrock-operator-group.yaml' >> ./logs/install_bedrock.log


result=$(oc apply -f bedrock-operator-group.yaml)
echo $result >> ./logs/install_bedrock.log
sleep 1m

# Create bedrock subscription. This will deploy the bedrock: 
sed -i -e s#BEDROCK_NAMESPACE#${BEDROCK_NAMESPACE}#g bedrock-sub.yaml

echo '*** executing **** oc apply -f bedrock-sub.yaml' >> ./logs/install_bedrock.log

result=$(oc apply -f bedrock-sub.yaml)
echo $result >> ./logs/install_bedrock.log
sleep 1m


#for reinstall, namespace-scope configmap will be deleted when ibm-common-service-operator first running. need to delete this pod to force recreate Configmap namespace-scope.
while true; do
# local cm_ns_status=$(oc get cm namespace-scope -n ibm-common-services)
cm_ns_status=$(oc get cm namespace-scope -n ${BEDROCK_NAMESPACE})
if [[ -n $cm_ns_status ]]; then
  echo "Config Map namespace-scope exist." >> ./logs/install_bedrock.log
  break
fi
sleep 30
oc get pods -n ${BEDROCK_NAMESPACE} -l name=ibm-common-service-operator | awk '{print $1}' | grep -Ev NAME | xargs oc delete pods -n ${BEDROCK_NAMESPACE}
sleep 30
done


echo "Waiting for Bedrock operator pods ready" >> ./logs/install_bedrock.log
while true; do
pod_status=$(oc get pods -n ${BEDROCK_NAMESPACE} | grep -Ev "NAME|1/1|2/2|3/3|5/5|Comp")
if [[ -z $pod_status ]]; then
  echo "All pods are running now" >> ./logs/install_bedrock.log
  break
fi
echo "Waiting for Bedrock operator pods ready" >> ./logs/install_bedrock.log
oc get pods -n ${BEDROCK_NAMESPACE}
sleep 30
if [[ `oc get po -n ${BEDROCK_NAMESPACE}` =~ "Error" ]]; then
  oc delete `oc get po -o name | grep ibm-common-service-operator`
else
  echo "No pods with Error" >> ./logs/install_bedrock.log
fi
done
  
sleep 60

oc patch NamespaceScope common-service -n ${BEDROCK_NAMESPACE} --type=merge --patch='{"spec": {"csvInjector": {"enable": true} } }'


# Checking if the bedrock operator pods are ready and running. 

# checking status of ibm-namespace-scope-operator

./check-subscription-status.sh ibm-common-service-operator ${BEDROCK_NAMESPACE} state
./pod-status-check.sh ibm-namespace-scope-operator ${BEDROCK_NAMESPACE}

# checking status of operand-deployment-lifecycle-manager

./pod-status-check.sh operand-deployment-lifecycle-manager ${BEDROCK_NAMESPACE}

# checking status of ibm-common-service-operator

./pod-status-check.sh ibm-common-service-operator ${BEDROCK_NAMESPACE}
