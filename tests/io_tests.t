# Deploy io-app deployment with 2 replicas
TEST "kubectl apply -f tests/test-io/io-app.yaml"

# Compressed image is ~25MB and so it shouldn't take much time to reach ready state
TEST "kubectl wait --for=condition=ready pod -l app=io-app --timeout=45s"

# Store pod names
pods = TEST "kubectl get pods -l app=io-app -o jsonpath={'..metadata.name'}"

puts "Run IO from first pod [~30s]"
# 9 types of IO operations are performed
TEST "kubectl exec -i ${pods[0]} -- sh -c 'cd /mnt/alpha; mkdir -p io-1; for j in create rename chmod chown chgrp symlink hardlink truncate setxattr create; do crefi --multi -n 5 -b 5 -d 5 --max=10K --min=500 --random -t text -T=3 --fop=$j io-1/ 2>/dev/null; done'"

puts "Run IO from second pod [~30s]"
TEST "kubectl exec -i ${pods[1]} -- sh -c 'cd /mnt/alpha; mkdir -p io-2; for j in create rename chmod chown chgrp symlink hardlink truncate setxattr create; do crefi --multi -n 5 -b 5 -d 5 --max=10K --min=500 --random -t text -T=3 --fop=$j io-2/ 2>/dev/null; done'"

puts "Collecting arequal-checksum from pods under io-pod deployment"
first_sum = TEST "kubectl exec -i ${pods[0]} -- sh -c 'arequal-checksum /mnt/alpha'"
puts first_sum
second_sum = TEST "kubectl exec -i ${pods[1]} -- sh -c 'arequal-checksum /mnt/alpha'"
puts second_sum

puts "Validate checksum between first and second pod [Empty for checksum match]"
TEST "diff <(echo \"#{first_sum}\") <(echo \"#{second_sum}\")"
