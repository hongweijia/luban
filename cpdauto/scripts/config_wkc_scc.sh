#!/bin/bash


CPD_INSTANCE_NAMESPACE=$1
# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/wkc-iis-scc.yaml wkc-iis-scc.yaml

mkdir -p ./logs
touch ./logs/config_wkc_scc.log
echo '' > ./logs/config_wkc_scc.log

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create customer SCC
oc delete scc wkc-iis-scc
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wkc-iis-scc.yaml
echo '*** executing **** oc apply -f wkc-iis-scc.yaml' >> ./logs/config_wkc_scc.log
result=$(oc apply -f wkc-iis-scc.yaml)
echo $result  >> ./logs/config_wkc_scc.log
sleep 1m

echo '*** Create the SCC cluster role for wkc-iis-scc **** ' >> ./logs/config_wkc_scc.log
result=$(oc create clusterrole system:openshift:scc:wkc-iis-scc --verb=use --resource=scc --resource-name=wkc-iis-scc)
echo $result  >> ./logs/config_wkc_scc.log

echo '*** Assign the wkc-iis-sa service account to the SCC cluster role **** ' >> ./logs/config_wkc_scc.log
result=$(oc create rolebinding wkc-iis-scc-rb --clusterrole=system:openshift:scc:wkc-iis-scc --serviceaccount=${CPD_INSTANCE_NAMESPACE}:wkc-iis-sa)
echo $result  >> ./logs/config_wkc_scc.log

echo '*** Confirm that the wkc-iis-sa service account can use the wkc-iis-scc SCC **** ' >> ./logs/config_wkc_scc.log
result=$(oc adm policy who-can use scc wkc-iis-scc -n ${CPD_INSTANCE_NAMESPACE} | grep "wkc-iis-sa")
echo $result  >> ./logs/config_wkc_scc.log
