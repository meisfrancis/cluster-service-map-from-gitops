import json
import csv

with open('clusters-services-mapping.json') as f:
    clusters_services_map = json.load(f)
with open('atlas-clusters.json') as f:
    atlas_clusters = json.load(f)
with open('cluster-links-map.json') as f:
    cluster_links_map = json.load(f)

# map service to atlas
for host, cluster in clusters_services_map.items():
    a_cluster = atlas_clusters.get(cluster_links_map.get(host))
    if a_cluster:
        if not a_cluster.get('services'):
            a_cluster['services'] = set()
            a_cluster['env'] = cluster['env']
        a_cluster['services'] = a_cluster['services'] | {x for x in cluster['services']}


# serialize data for csv
for cluster in atlas_clusters.values():
    cluster['nodes'] = '\n'.join(cluster['node_links'])
    cluster['rate'] = len(cluster.get('services', []))
    cluster['services'] = '\n'.join(cluster.get('services', []))

with open('result.csv', 'w', newline='') as csvfile:
    data = list(atlas_clusters.values())
    field_names = data[0].keys()
    writer = csv.DictWriter(csvfile, fieldnames=field_names)

    writer.writeheader()
    writer.writerows(data)




