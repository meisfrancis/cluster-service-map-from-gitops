import json
import yaml
import os
import sys
import subprocess
import re

os.environ['AWS_PROFILE'] = 'setel'

GITOPS_ROOT_DIR = '/Volumes/Work/code/setel/SRE/gitops'
MONGODB_SHARED_SUB_DIR = 'mongodb-shared'

environment = sys.argv[1]

ClusterHostNameKey = str
ClusterHostVal = str
ClusterServiceMap = dict[ClusterHostVal, dict['services', set[str]]]
SecretDict = dict[ClusterHostNameKey, ClusterHostVal]
OnlyHostSecretDict = SecretDict


def load_mongo_secret() -> SecretDict:
    mongoshare_root_dir = os.path.join(GITOPS_ROOT_DIR, MONGODB_SHARED_SUB_DIR)
    secret_dict = {}
    for root, dirs, files in os.walk(mongoshare_root_dir):
        # Because the format inside mongodb-shared is not consistent, we will loop all subdirectories matching the env
        for dir in dirs:
            if dir == environment:
                secret_path = os.path.join(root, dir, 'aws/apse1')
                yaml_secret = subprocess.check_output(f'sops -d {secret_path}/secret.enc.yaml'.split(' '))
                secret_dict = secret_dict | yaml.safe_load(yaml_secret)['stringData']
    return secret_dict


def generate_name_host_dict(data: SecretDict) -> tuple[OnlyHostSecretDict, ClusterServiceMap]:
    cluster_list = {}
    mongodb_hosts = {}
    for k, v in data.items():
        if re.search(r'.*HOSTNAME.*', k):
            mongodb_hosts[k] = v
            if not cluster_list.get(v):
                cluster_list[v] = {
                    "services": set()
                }
    return mongodb_hosts, cluster_list


def map_services_to_host(data: SecretDict) -> ClusterServiceMap:
    mongodb_hosts, cluster_list = generate_name_host_dict(data)
    for root, *_ in os.walk(GITOPS_ROOT_DIR):
        for _root, __, _files in os.walk(root):
            # Only dive to dirs having files and not being mongodb-shared
            if _files and not re.search(r'(mongodb-shared|\.)', _root):
                for _file in _files:
                    with open(os.path.join(_root, _file)) as f:
                        try:
                            content = f.read()
                        except UnicodeDecodeError:
                            print('error')
                        hosts = set(re.findall(r'([A-Z0-9_]+_HOSTNAME_[A-Z0-9_]+)', content))
                        app_name_label = re.search(r'gitops/([^/]+)/', _root)
                        if hosts and app_name_label:
                            app_name = app_name_label.groups()[0].strip()
                            if app_name == 'mongodb-shared':
                                print(app_name)
                            for host in hosts:
                                host_name = mongodb_hosts.get(host)
                                if host_name and app_name:
                                    cluster_list[host_name]['services'].add(app_name)
    for k, v in cluster_list.items():
        v['services'] = list(v['services'])
    return cluster_list


mongo_secret = load_mongo_secret()
cluster_service_map = map_services_to_host(mongo_secret)
with open(f'{environment}-clusters-services-mapping.json', 'w') as f:
    json.dump(cluster_service_map, f)
