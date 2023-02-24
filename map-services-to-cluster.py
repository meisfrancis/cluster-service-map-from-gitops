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

# Load dirs
mongodb_secret_dirs: list[str] = []
gitops_services_files: list[str] = []
for root, dirs, files in os.walk(GITOPS_ROOT_DIR):
    if re.search(f'{MONGODB_SHARED_SUB_DIR}(/.+)?/{environment}/aws/apse1', root):
        mongodb_secret_dirs.append(root)
    if not re.search(f'({MONGODB_SHARED_SUB_DIR}|\\.)', root) and files:
        for file in files:
            # ignore encrypted files
            if not re.search(r'\.enc\.ya?ml', file):
                gitops_services_files.append(os.path.join(root, file))


def load_mongo_secret() -> SecretDict:
    secret_dict = {}
    for dir in mongodb_secret_dirs:
        yaml_secret = subprocess.check_output(f'sops -d {dir}/secret.enc.yaml'.split(' '))
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
    for gitops_file_path in gitops_services_files:
        with open(gitops_file_path) as f:
            try:
                content = f.read()
            except UnicodeDecodeError:
                print('error')
            hosts = set(re.findall(r'([A-Z0-9_]+_HOSTNAME_[A-Z0-9_]+)', content))
            app_name_label = re.search(r'gitops/([^/]+)/', gitops_file_path)
            if hosts and app_name_label:
                app_name = app_name_label.groups()[0].strip()
                for host_name in (mongodb_hosts.get(host) for host in hosts if app_name):
                    cluster_list[host_name]['services'].add(app_name)

    for k, v in cluster_list.items():
        v['services'] = list(v['services'])
    return cluster_list


mongo_secret = load_mongo_secret()
cluster_service_map = map_services_to_host(mongo_secret)
with open(f'{environment}-clusters-services-mapping.json', 'w') as f:
    json.dump(cluster_service_map, f)
