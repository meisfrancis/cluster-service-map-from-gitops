import json
import yaml
import os
import sys
import subprocess
import re

os.environ['AWS_PROFILE'] = 'setel'

GITOPS_ROOT_DIR = '/Volumes/Work/code/setel/SRE/gitops'
MONGODB_SHARED_SUB_DIR = 'mongodb-shared'
ENVIRONMENT = ['dev', 'pre-prod', 'prod', 'staging', 'sandbox']

ProjectName = str
ClusterHostVarName = str
ClusterHostUri = str
ClusterServiceMap = dict[ClusterHostUri, dict['services', set[str]]]
SecretDict = dict[ENVIRONMENT, dict[ProjectName, ClusterServiceMap]]
OnlyHostSecretDict = SecretDict

# Load dirs
mongodb_secret_dirs: list[str] = []
gitops_services_files: list[str] = []
for root, dirs, files in os.walk(GITOPS_ROOT_DIR):
    if re.search(f"{MONGODB_SHARED_SUB_DIR}(/.+)?/({'|'.join(ENVIRONMENT)})/aws/apse1", root):
        mongodb_secret_dirs.append(root)
    if not re.search(f'({MONGODB_SHARED_SUB_DIR}|\\.)', root) and files:
        for file in files:
            # ignore encrypted files
            if not re.search(r'\.enc\.ya?ml', file):
                gitops_services_files.append(os.path.join(root, file))


def load_mongo_secret() -> SecretDict:
    secret_dict = {k: {} for k in ENVIRONMENT}
    for dir in mongodb_secret_dirs:
        yaml_secret = subprocess.check_output(f'sops -d {dir}/secret.enc.yaml'.split(' '))
        project_name, environment, *_ = re.search(f"/([^/]+)/({'|'.join(ENVIRONMENT)})/aws/apse1", dir).groups()
        if project_name == MONGODB_SHARED_SUB_DIR:
            project_name = 'b2c'
        if not secret_dict[environment].get(project_name):
            secret_dict[environment][project_name] = {k: v for k, v in yaml.safe_load(yaml_secret)['stringData'].items()
                                                      if 'HOSTNAME' in k}

    return secret_dict


def generate_name_host_dict(data: SecretDict) -> ClusterServiceMap:
    cluster_list = {}
    for projects in data.values():
        for cluster_details in projects.values():
            for val in cluster_details.values():
                if not cluster_list.get(val):
                    cluster_list[val] = {
                        "services": set()
                    }
    return cluster_list


def find_host(data: SecretDict, host_name: ClusterHostVarName) -> list[ClusterHostUri]:
    hosts = set()
    for projects in data.values():
        for cluster_details in projects.values():
            for k in cluster_details:
                if k == host_name:
                    hosts.add(cluster_details[k])

    return hosts


def map_services_to_host(data: SecretDict) -> ClusterServiceMap:
    cluster_list = generate_name_host_dict(data)
    for gitops_file_path in gitops_services_files:
        with open(gitops_file_path) as f:
            try:
                content = f.read()
            except UnicodeDecodeError:
                print('error')
            host_vars = set(re.findall(r'([A-Z0-9_]+_HOSTNAME_[A-Z0-9_]+)', content))
            app_name_label = re.search(r'gitops/([^/]+)/', gitops_file_path)
            if host_vars and app_name_label:
                app_name = app_name_label.groups()[0].strip()
                hosts = [x for host_var in host_vars for x in find_host(data, host_var) if app_name]
                for host in hosts:
                    cluster_list[host]['services'].add(app_name)

    for k, v in cluster_list.items():
        v['services'] = list(v['services'])
    return cluster_list


def main():
    mongo_secret = load_mongo_secret()
    cluster_service_map = map_services_to_host(mongo_secret)
    with open('clusters-services-mapping.json', 'w') as f:
        json.dump(cluster_service_map, f)


main()
