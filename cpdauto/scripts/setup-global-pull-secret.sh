#!/bin/bash

IMAGE_REGISTRY_URL=$1
IMAGE_REGISTRY_USER=$2
IMAGE_REGISTRY_PASSWORD=$3

AUTH=$(echo -n "$IMAGE_REGISTRY_USER:$IMAGE_REGISTRY_PASSWORD" | base64 -w0)

CUST_REG='{"%s": {"auth":"%s", "email":"%s"}}\n'
printf "$CUST_REG" "$IMAGE_REGISTRY_URL" "$AUTH" "not-used" > /tmp/local_reg.json

# Retrieve the current global pull secret
oc get secret/pull-secret -n openshift-config -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d > /tmp/dockerconfig.json

jq --argjson authinfo "$(</tmp/local_reg.json)" '.auths += $authinfo' /tmp/dockerconfig.json > /tmp/global_pull_secret.json

oc set data secret/pull-secret -n openshift-config --from-file=.dockerconfigjson=/tmp/global_pull_secret.json

sleep 15m

#Add the private registry to the insecureRegistries list
oc patch image.config.openshift.io/cluster -p "{\"spec\":{\"registrySources\":{\"insecureRegistries\":[\"$IMAGE_REGISTRY_URL\"]}}}" --type='merge'
sleep 15m

# take a backup of dockerconfig.json after private image registry secret added. 
cp /tmp/global_pull_secret.json /tmp/global_pull_secret.json_backup