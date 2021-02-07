import os
import time
import logging

from prometheus_client.core import GaugeMetricFamily, \
     CounterMetricFamily, REGISTRY
from prometheus_client import start_http_server

from volumeutils import HOSTVOL_MOUNTDIR
from kadalulib import logging_setup, logf


class CsiMetricsCollector(object):
    def collect(self):
        # TODO: Add more labels
        capacity_labels = ['storage_name']
        capacity_bytes = GaugeMetricFamily(
            'kadalu_storage_capacity_bytes',
            'Kadalu Storage Capacity',
            labels=capacity_labels
        )
        capacity_used_bytes = GaugeMetricFamily(
            'kadalu_storage_capacity_used_bytes',
            'Kadalu Storage Used Capacity',
            labels=capacity_labels
        )
        capacity_free_bytes = GaugeMetricFamily(
            'kadalu_storage_capacity_free_bytes',
            'Kadalu Storage Free Capacity',
            labels=capacity_labels
        )
        inodes_count = CounterMetricFamily(
            'kadalu_storage_inodes_count',
            'Kadalu Storage Inodes Count',
            labels=capacity_labels
        )
        inodes_used_count = CounterMetricFamily(
            'kadalu_storage_inodes_used_count',
            'Kadalu Storage Inodes used Count',
            labels=capacity_labels
        )
        inodes_free_count = CounterMetricFamily(
            'kadalu_storage_inodes_free_count',
            'Kadalu Storage Inodes free Count',
            labels=capacity_labels
        )

        for dirname in os.listdir(HOSTVOL_MOUNTDIR):
            labels = [dirname]  # TODO: Add more labels
            pth = os.path.join(HOSTVOL_MOUNTDIR, dirname)
            if os.path.ismount(pth):
                stat = os.statvfs(pth)

                # Capacity
                total = stat.f_bsize * stat.f_blocks
                free = stat.f_bsize * stat.f_bavail
                used = total - free
                capacity_bytes.add_metric(labels, total)
                capacity_free_bytes.add_metric(labels, free)
                capacity_used_bytes.add_metric(labels, used)

                # Inodes
                total = stat.f_files
                free = stat.f_favail
                used = total - free
                inodes_count.add_metric(labels, total)
                inodes_free_count.add_metric(labels, free)
                inodes_used_count.add_metric(labels, used)

        yield capacity_bytes
        yield capacity_free_bytes
        yield capacity_used_bytes
        yield inodes_count
        yield inodes_free_count
        yield inodes_used_count


REGISTRY.register(CsiMetricsCollector())


if __name__ == "__main__":
    logging_setup()

    start_http_server(8000)
    logging.info(
        logf("Started Kadalu Storage CSI Metrics exporter.", port=8000)
    )

    while True:
        time.sleep(5)
