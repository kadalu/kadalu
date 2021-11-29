cmd = "python3 cli/kubectl_kadalu"

def diff(expected, actual)
  "Expected:\n#{expected}\n\nActual:\n#{actual}\n"
end

def EQUAL(expected, actual, desc)
  TRUE expected == actual, desc, diff(expected, actual)
end

# External Storage Pool
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "External"
  storage: []
  details:
    gluster_hosts: ['server1.example.com']
    gluster_volname: "exports/sp1/s1"
    gluster_options: ""

)
actual = TEST "#{cmd} storage-add --dry-run sp1 external server1.example.com:/exports/sp1/s1"
EQUAL expected, actual, "external as keyword"

actual = TEST "#{cmd} storage-add --dry-run sp1 --external server1.example.com:/exports/sp1/s1"
EQUAL expected, actual, "with --external flag"

# Replica1 with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica1"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --path server1.example.com:/exports/sp1/s1"
EQUAL expected, actual, "Auto Replica1 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica1 --path server1.example.com:/exports/sp1/s1"
EQUAL expected, actual, "Replica1 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 server1.example.com:/exports/sp1/s1 --storage-unit-type=path"
EQUAL expected, actual, "Auto Replica1 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/exports/sp1/s1 --storage-unit-type=path"
EQUAL expected, actual, "Replica1 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 1 server1.example.com:/exports/sp1/s1 --storage-unit-type=path"
EQUAL expected, actual, "Replica1 with alternate syntax 2 and --storage-unit-type=path"

# Replica1 with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica1"
  storage:
    - pvc: "pvc1"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --pvc pvc1"
EQUAL expected, actual, "Auto Replica1 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica1 --pvc pvc1"
EQUAL expected, actual, "Replica1 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 pvc1 --storage-unit-type=pvc"
EQUAL expected, actual, "Auto Replica1 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica pvc1 --storage-unit-type=pvc"
EQUAL expected, actual, "Replica1 with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 1 pvc1 --storage-unit-type=pvc"
EQUAL expected, actual, "Replica1 with alternate syntax 2 and --storage-unit-type=pvc"

# Replica1 with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica1"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --device server1.example.com:/dev/vdc"
EQUAL expected, actual, "Auto Replica1 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica1 --device server1.example.com:/dev/vdc"
EQUAL expected, actual, "Replica1 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 server1.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Auto Replica1 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Replica1 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 1 server1.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Replica1 with alternate syntax 2 and --storage-unit-type=device"

# Replica2 with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica2"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica2 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2"
EQUAL expected, actual, "Replica2 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 --storage-unit-type=path"
EQUAL expected, actual, "Replica2 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 2 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 --storage-unit-type=path"
EQUAL expected, actual, "Replica2 with alternate syntax 2 and --storage-unit-type=path"

# Replica2 with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica2"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica2 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc"
EQUAL expected, actual, "Replica2 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/dev/vdc server2.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Replica2 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 2 server1.example.com:/dev/vdc server2.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Replica2 with alternate syntax 2 and --storage-unit-type=device"

# Replica2 with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica2"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica2 --pvc pvc1 --pvc pvc2"
EQUAL expected, actual, "Replica2 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica pvc1 pvc2 --storage-unit-type=pvc"
EQUAL expected, actual, "Replica2 with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 2 pvc1 pvc2 --storage-unit-type=pvc"
EQUAL expected, actual, "Replica2 with alternate syntax 2 and --storage-unit-type=pvc"


# Replica3 with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica3"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"
    - node: "server3.example.com"
      path: "/exports/sp1/s3"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica3 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2 --path server3.example.com:/exports/sp1/s3"
EQUAL expected, actual, "Replica3 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 --storage-unit-type=path"
EQUAL expected, actual, "Replica3 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 3 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 --storage-unit-type=path"
EQUAL expected, actual, "Replica3 with alternate syntax 2 and --storage-unit-type=path"

# Replica3 with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica3"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"
    - node: "server3.example.com"
      device: "/dev/vdc"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica3 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc --device server3.example.com:/dev/vdc"
EQUAL expected, actual, "Replica3 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Replica3 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 3 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Replica3 with alternate syntax 2 and --storage-unit-type=device"

# Replica3 with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica3"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"
    - pvc: "pvc3"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica3 --pvc pvc1 --pvc pvc2 --pvc pvc3"
EQUAL expected, actual, "Replica3 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica pvc1 pvc2 pvc3 --storage-unit-type=pvc"
EQUAL expected, actual, "Replica3 with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 3 pvc1 pvc2 pvc3 --storage-unit-type=pvc"
EQUAL expected, actual, "Replica3 with alternate syntax 2 and --storage-unit-type=pvc"


# Disperse with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Disperse"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"
    - node: "server3.example.com"
      path: "/exports/sp1/s3"
  disperse:
    data: 2
    redundancy: 1

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Disperse --data 2 --redundancy 1 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2 --path server3.example.com:/exports/sp1/s3"
EQUAL expected, actual, "Disperse with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 redundancy server3.example.com:/exports/sp1/s3 --storage-unit-type=path"
EQUAL expected, actual, "Disperse with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 redundancy 1 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 --storage-unit-type=path"
EQUAL expected, actual, "Disperse(disperse & redundancy) with alternate syntax 2 and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data 2 redundancy 1 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 --storage-unit-type=path"
EQUAL expected, actual, "Disperse(disperse-data & redundancy) with alternate syntax 2 and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 disperse-data 2 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 --storage-unit-type=path"
EQUAL expected, actual, "Disperse(disperse & disperse-data) with alternate syntax 2 and --storage-unit-type=path"


# Disperse with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Disperse"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"
    - node: "server3.example.com"
      device: "/dev/vdc"
  disperse:
    data: 2
    redundancy: 1

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Disperse --data 2 --redundancy 1 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc --device server3.example.com:/dev/vdc"
EQUAL expected, actual, "Disperse with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data server1.example.com:/dev/vdc server2.example.com:/dev/vdc redundancy server3.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Disperse with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 redundancy 1 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Disperse(disperse & redundancy) with alternate syntax 2 and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data 2 redundancy 1 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Disperse(disperse-data & redundancy) with alternate syntax 2 and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 disperse-data 2 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Disperse(disperse & disperse-data) with alternate syntax 2 and --storage-unit-type=device"

# Disperse with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Disperse"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"
    - pvc: "pvc3"
  disperse:
    data: 2
    redundancy: 1

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Disperse --data 2 --redundancy 1 --pvc pvc1 --pvc pvc2 --pvc pvc3"
EQUAL expected, actual, "Disperse with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data pvc1 pvc2 redundancy pvc3 --storage-unit-type=pvc"
EQUAL expected, actual, "Disperse with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 redundancy 1 pvc1 pvc2 pvc3 --storage-unit-type=pvc"
EQUAL expected, actual, "Disperse(disperse & redundancy) with alternate syntax 2 and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data 2 redundancy 1 pvc1 pvc2 pvc3 --storage-unit-type=pvc"
EQUAL expected, actual, "Disperse(disperse-data & redundancy) with alternate syntax 2 and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 disperse-data 2 pvc1 pvc2 pvc3 --storage-unit-type=pvc"
EQUAL expected, actual, "Disperse(disperse & disperse-data) with alternate syntax 2 and --storage-unit-type=pvc"

# Distributed Storage Pool tests
# Distributed Replica1 with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica1"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2"
EQUAL expected, actual, "Auto Distributed Replica1 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica1 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2"
EQUAL expected, actual, "Distributed Replica1 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 --storage-unit-type=path"
EQUAL expected, actual, "Auto Distributed Replica1 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/exports/sp1/s1 replica server2.example.com:/exports/sp1/s2 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Replica1 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 1 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Replica1 with alternate syntax 2 and --storage-unit-type=path"

# Distributed Replica1 with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica1"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --pvc pvc1 --pvc pvc2"
EQUAL expected, actual, "Auto Distributed Replica1 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica1 --pvc pvc1 --pvc pvc2"
EQUAL expected, actual, "Distributed Replica1 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 pvc1 pvc2 --storage-unit-type=pvc"
EQUAL expected, actual, "Auto Distributed Replica1 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica pvc1 replica pvc2 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Replica1 with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 1 pvc1 pvc2 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Replica1 with alternate syntax 2 and --storage-unit-type=pvc"

# Distributed Replica1 with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica1"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc"
EQUAL expected, actual, "Auto Distributed Replica1 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica1 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc"
EQUAL expected, actual, "Distributed Replica1 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 server1.example.com:/dev/vdc server2.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Auto Replica1 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/dev/vdc replica server2.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Replica1 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 1 server1.example.com:/dev/vdc server2.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Replica1 with alternate syntax 2 and --storage-unit-type=device"

# Replica2 with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica2"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"
    - node: "server3.example.com"
      path: "/exports/sp1/s3"
    - node: "server4.example.com"
      path: "/exports/sp1/s4"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica2 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2 --path server3.example.com:/exports/sp1/s3 --path server4.example.com:/exports/sp1/s4"
EQUAL expected, actual, "Distributed Replica2 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 replica server3.example.com:/exports/sp1/s3 server4.example.com:/exports/sp1/s4 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Replica2 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 2 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 server4.example.com:/exports/sp1/s4 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Replica2 with alternate syntax 2 and --storage-unit-type=path"

# Replica2 with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica2"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"
    - node: "server3.example.com"
      device: "/dev/vdc"
    - node: "server4.example.com"
      device: "/dev/vdc"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica2 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc --device server3.example.com:/dev/vdc --device server4.example.com:/dev/vdc"
EQUAL expected, actual, "Distributed Replica2 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/dev/vdc server2.example.com:/dev/vdc replica server3.example.com:/dev/vdc server4.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Replica2 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 2 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc server4.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Replica2 with alternate syntax 2 and --storage-unit-type=device"

# Replica2 with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica2"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"
    - pvc: "pvc3"
    - pvc: "pvc4"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica2 --pvc pvc1 --pvc pvc2 --pvc pvc3 --pvc pvc4"
EQUAL expected, actual, "Distributed Replica2 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica pvc1 pvc2 replica pvc3 pvc4 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Replica2 with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 2 pvc1 pvc2 pvc3 pvc4 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Replica2 with alternate syntax 2 and --storage-unit-type=pvc"

# Replica3 with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica3"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"
    - node: "server3.example.com"
      path: "/exports/sp1/s3"
    - node: "server4.example.com"
      path: "/exports/sp1/s4"
    - node: "server5.example.com"
      path: "/exports/sp1/s5"
    - node: "server6.example.com"
      path: "/exports/sp1/s6"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica3 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2 --path server3.example.com:/exports/sp1/s3 --path server4.example.com:/exports/sp1/s4 --path server5.example.com:/exports/sp1/s5 --path server6.example.com:/exports/sp1/s6"
EQUAL expected, actual, "Distributed Replica3 with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 replica server4.example.com:/exports/sp1/s4 server5.example.com:/exports/sp1/s5 server6.example.com:/exports/sp1/s6 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Replica3 with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 3 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 server4.example.com:/exports/sp1/s4 server5.example.com:/exports/sp1/s5 server6.example.com:/exports/sp1/s6 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Replica3 with alternate syntax 2 and --storage-unit-type=path"

# Replica3 with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica3"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"
    - node: "server3.example.com"
      device: "/dev/vdc"
    - node: "server4.example.com"
      device: "/dev/vdc"
    - node: "server5.example.com"
      device: "/dev/vdc"
    - node: "server6.example.com"
      device: "/dev/vdc"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica3 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc --device server3.example.com:/dev/vdc --device server4.example.com:/dev/vdc --device server5.example.com:/dev/vdc --device server6.example.com:/dev/vdc"
EQUAL expected, actual, "Distributed Replica3 with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc replica server4.example.com:/dev/vdc server5.example.com:/dev/vdc server6.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Replica3 with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 3 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc server4.example.com:/dev/vdc server5.example.com:/dev/vdc server6.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Replica3 with alternate syntax 2 and --storage-unit-type=device"

# Replica3 with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Replica3"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"
    - pvc: "pvc3"
    - pvc: "pvc4"
    - pvc: "pvc5"
    - pvc: "pvc6"

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Replica3 --pvc pvc1 --pvc pvc2 --pvc pvc3 --pvc pvc4 --pvc pvc5 --pvc pvc6"
EQUAL expected, actual, "Distributed Replica3 with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica pvc1 pvc2 pvc3 replica pvc4 pvc5 pvc6 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Replica3 with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 replica 3 pvc1 pvc2 pvc3 pvc4 pvc5 pvc6 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Replica3 with alternate syntax 2 and --storage-unit-type=pvc"


# Distributed Disperse with path
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Disperse"
  storage:
    - node: "server1.example.com"
      path: "/exports/sp1/s1"
    - node: "server2.example.com"
      path: "/exports/sp1/s2"
    - node: "server3.example.com"
      path: "/exports/sp1/s3"
    - node: "server4.example.com"
      path: "/exports/sp1/s4"
    - node: "server5.example.com"
      path: "/exports/sp1/s5"
    - node: "server6.example.com"
      path: "/exports/sp1/s6"
  disperse:
    data: 2
    redundancy: 1

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Disperse --data 2 --redundancy 1 --path server1.example.com:/exports/sp1/s1 --path server2.example.com:/exports/sp1/s2 --path server3.example.com:/exports/sp1/s3 --path server4.example.com:/exports/sp1/s4 --path server5.example.com:/exports/sp1/s5 --path server6.example.com:/exports/sp1/s6"
EQUAL expected, actual, "Distributed Disperse with --path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 redundancy server3.example.com:/exports/sp1/s3 disperse-data server4.example.com:/exports/sp1/s4 server5.example.com:/exports/sp1/s5 redundancy server6.example.com:/exports/sp1/s6 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Disperse with alternate syntax and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 redundancy 1 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 server4.example.com:/exports/sp1/s4 server5.example.com:/exports/sp1/s5 server6.example.com:/exports/sp1/s6 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Disperse(disperse & redundancy) with alternate syntax 2 and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data 2 redundancy 1 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 server4.example.com:/exports/sp1/s4 server5.example.com:/exports/sp1/s5 server6.example.com:/exports/sp1/s6 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Disperse(disperse-data & redundancy) with alternate syntax 2 and --storage-unit-type=path"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 disperse-data 2 server1.example.com:/exports/sp1/s1 server2.example.com:/exports/sp1/s2 server3.example.com:/exports/sp1/s3 server4.example.com:/exports/sp1/s4 server5.example.com:/exports/sp1/s5 server6.example.com:/exports/sp1/s6 --storage-unit-type=path"
EQUAL expected, actual, "Distributed Disperse(disperse & disperse-data) with alternate syntax 2 and --storage-unit-type=path"


# Distributed Disperse with device
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Disperse"
  storage:
    - node: "server1.example.com"
      device: "/dev/vdc"
    - node: "server2.example.com"
      device: "/dev/vdc"
    - node: "server3.example.com"
      device: "/dev/vdc"
    - node: "server4.example.com"
      device: "/dev/vdc"
    - node: "server5.example.com"
      device: "/dev/vdc"
    - node: "server6.example.com"
      device: "/dev/vdc"
  disperse:
    data: 2
    redundancy: 1

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Disperse --data 2 --redundancy 1 --device server1.example.com:/dev/vdc --device server2.example.com:/dev/vdc --device server3.example.com:/dev/vdc --device server4.example.com:/dev/vdc --device server5.example.com:/dev/vdc --device server6.example.com:/dev/vdc"
EQUAL expected, actual, "Distributed Disperse with --device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data server1.example.com:/dev/vdc server2.example.com:/dev/vdc redundancy server3.example.com:/dev/vdc disperse-data server4.example.com:/dev/vdc server5.example.com:/dev/vdc redundancy server6.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Disperse with alternate syntax and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 redundancy 1 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc server4.example.com:/dev/vdc server5.example.com:/dev/vdc server6.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Disperse(disperse & redundancy) with alternate syntax 2 and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data 2 redundancy 1 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc server4.example.com:/dev/vdc server5.example.com:/dev/vdc server6.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Disperse(disperse-data & redundancy) with alternate syntax 2 and --storage-unit-type=device"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 disperse-data 2 server1.example.com:/dev/vdc server2.example.com:/dev/vdc server3.example.com:/dev/vdc server4.example.com:/dev/vdc server5.example.com:/dev/vdc server6.example.com:/dev/vdc --storage-unit-type=device"
EQUAL expected, actual, "Distributed Disperse(disperse & disperse-data) with alternate syntax 2 and --storage-unit-type=device"

# Disperse with pvc
expected = %(Storage Yaml file for your reference:

apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "sp1"
spec:
  type: "Disperse"
  storage:
    - pvc: "pvc1"
    - pvc: "pvc2"
    - pvc: "pvc3"
    - pvc: "pvc4"
    - pvc: "pvc5"
    - pvc: "pvc6"
  disperse:
    data: 2
    redundancy: 1

)

actual = TEST "#{cmd} storage-add --dry-run sp1 --type=Disperse --data 2 --redundancy 1 --pvc pvc1 --pvc pvc2 --pvc pvc3 --pvc pvc4 --pvc pvc5 --pvc pvc6"
EQUAL expected, actual, "Distributed Disperse with --pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data pvc1 pvc2 redundancy pvc3 disperse-data pvc4 pvc5 redundancy pvc6 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Disperse with alternate syntax and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 redundancy 1 pvc1 pvc2 pvc3 pvc4 pvc5 pvc6 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Disperse(disperse & redundancy) with alternate syntax 2 and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse-data 2 redundancy 1 pvc1 pvc2 pvc3 pvc4 pvc5 pvc6 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Disperse(disperse-data & redundancy) with alternate syntax 2 and --storage-unit-type=pvc"

actual = TEST "#{cmd} storage-add --dry-run sp1 disperse 3 disperse-data 2 pvc1 pvc2 pvc3 pvc4 pvc5 pvc6 --storage-unit-type=pvc"
EQUAL expected, actual, "Distributed Disperse(disperse & disperse-data) with alternate syntax 2 and --storage-unit-type=pvc"
