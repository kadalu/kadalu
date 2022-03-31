from prometheus_client import Gauge

memory_usage = Gauge('kadalu_memory_usage_in_bytes', 'Kadalu Memory Usage in Bytes', ['name'])
cpu_usage = Gauge('kadalu_cpu_usage_in_ns', 'Kadalu Memory Usage in Nanoseconds', ['name'])

total_number_of_containers = Gauge('kadalu_total_number_of_containers', 'Kadalu Total Number Of Containers', ['name'])
number_of_ready_containers = Gauge('kadalu_total_number_of_ready_containers', 'Kadalu Total Number Of Ready Containers', ['name'])

total_capacity_bytes = Gauge('kadalu_storage_total_capacity_bytes', 'Kadalu Total Storage Capacity', ['name'])
used_capacity_bytes = Gauge('kadalu_storage_used_capacity_bytes', 'Kadalu Total Storage Used Capacity', ['name'])
free_capacity_bytes = Gauge('kadalu_storage_free_capacity_bytes', 'Kadalu Total Storage Free Capacity', ['name'])

total_inodes = Gauge('kadalu_storage_total_inodes', 'Kadalu Total Storage Inodes', ['name'])
used_inodes = Gauge('kadalu_storage_used_inodes', 'Kadalu Total Storage Inodes Used', ['name'])
free_inodes = Gauge('kadalu_storage_free_inodes', 'Kadalu Total Storage Inodes Free', ['name'])

total_pvc_capacity_bytes = Gauge('kadalu_pvc_total_capacity_bytes', 'Kadalu Total PVC Capacity', ['name'])
used_pvc_capacity_bytes = Gauge('kadalu_pvc_used_capacity_bytes', 'Kadalu Total PVC Used Capacity', ['name'])
free_pvc_capacity_bytes = Gauge('kadalu_pvc_free_capacity_bytes', 'Kadalu Total PVC Free Capacity', ['name'])

total_pvc_inodes = Gauge('kadalu_pvc_total_inodes', 'Kadalu Total Total PVC Inodes', ['name'])
used_pvc_inodes = Gauge('kadalu_pvc_used_inodes', 'Kadalu Total Used PVC Inodes', ['name'])
free_pvc_inodes = Gauge('kadalu_pvc_free_inodes', 'Kadalu Total Free PVC Inodes', ['name'])
