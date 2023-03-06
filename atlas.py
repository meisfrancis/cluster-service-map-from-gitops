import asyncio
import json

orgs = {}
projects = {}
clusters = {}
cluster_links_map = {}
atlat_url_tpl = 'https://cloud.mongodb.com/v2/{project_id}#/clusters/detail/{cluster_name}'


async def fetch_atlas(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
    )

    stdout, _ = await proc.communicate()
    result = json.loads(stdout.decode())
    return result.get('results', [])


def rs_filter(d, keys):
    return {key: val for key, val in d.items() if key in keys}


async def get_orgs():
    result = await fetch_atlas('atlas organizations list -o json')
    global orgs
    orgs = {item['id']: {k: v for k, v in item.items() if k in ['id', 'name']} for item in result}


async def get_projects():
    result = await fetch_atlas('atlas projects list -o json')
    global projects
    projects = {item['id']: {k: v for k, v in item.items() if k in ['id', 'name', 'orgId']} for item in result}
    for v in projects.values():
        v['breadcrumb'] = f"{orgs[v['orgId']]['name']} / {v['name']}"


async def attach_clusters(project_id):
    result = await fetch_atlas(f'atlas clusters list --projectId {project_id} -o json')
    global clusters
    for item in result:
        host_cutter = lambda x: x.split('mongodb+srv://')[1]
        cluster_links = [
            host_cutter(link.get('srvConnectionString', '')) for link
            in item['connectionStrings']
            .get('privateEndpoint', [])
            if link
        ]
        cluster_links.append(host_cutter(item['connectionStrings']['standardSrv']))
        clusters = clusters | {
            item['name']: {
                              k: v for k, v in item.items() if k in ['name', 'groupId']
                          } |
                          {
                              'node_links': cluster_links
                          } |
                          {
                              'atlas_url': atlat_url_tpl.format(project_id=item['groupId'], cluster_name=item['name'])
                          }
        }
        global cluster_links_map
        cluster_links_map = cluster_links_map | {link: item['name'] for link in cluster_links}


async def main():
    await get_orgs()
    await get_projects()
    await asyncio.gather(*[attach_clusters(k) for k, v in projects.items()])
    for v in clusters.values():
        v['breadcrumb'] = f"{projects[v['groupId']]['breadcrumb']} / {v['name']}"
    with open('atlas-clusters.json', 'w') as f:
        json.dump(clusters, f)
    with open('cluster-links-map.json', 'w') as f:
        json.dump(cluster_links_map, f)


asyncio.run(main())
