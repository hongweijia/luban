#!/bin/bash

IMAGE_REGISTRY_URL=$1

# # Clone yaml files from the templates
if [[ $(type -t cp) == "alias" ]]
then
  unalias cp
  echo "unalias cp completed."
fi
cp ./templates/cpd/image_content_source_policy.yaml image_content_source_policy.yaml

sed -i -e s#PRIVATE_REGISTRY#${IMAGE_REGISTRY_URL}#g image_content_source_policy.yaml

mkdir -p ./logs
touch ./logs/setup-img-content-source-policy.log
echo '' > ./logs/setup-img-content-source-policy.log

echo '*** delete existing imagecontentsourcepolicy cloud-pak-for-data-mirror' >> ./logs/setup-img-content-source-policy.log
for p in $(oc get imagecontentsourcepolicy | grep cloud-pak-for-data-mirror| awk '{print $1}') ; do oc delete imagecontentsourcepolicy $p; done

echo '*** executing **** oc apply -f image_content_source_policy.yaml' >> ./logs/setup-img-content-source-policy.log
result=$(oc apply -f image_content_source_policy.yaml)
echo $result >> ./logs/setup-img-content-source-policy.log
sleep 15m