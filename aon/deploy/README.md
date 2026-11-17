# `deploy/`
This directory contains definitions, manifests, and scripts relating specifcally to the deployment/devliery of the 
application through automated means.

### `k8s/`
Holds the base manifest, and profile overlays that are used to generate build specific deployment manifests.

### `tests/`
Container structure test definitions. These tests are run after the build artifacts and manifests are generated.
These tests validate that the build artifact that will be deployed passes a set of tests, ideally including the unit
tests. 

See: https://github.com/GoogleContainerTools/container-structure-test

### `cloudbuild.yaml`
Defines the build pipeline to be run  automatically in GCP.

### `Dockerfile`
Docker image build definition file. Defines how the docker image should be built.

### `entrypoint.sh`
Standardized entrypoint for container images. Prints system, storage, and cpu information, performs startup tasks
(e.g. django's `collectstatic` or `migrate` operations), and identifies itself with a "mascot" to make it easy to
determine which logs you're looking at.

## Viewing Logs with Kubectl and Kubernetes


### Set the Kubectl Context
To change the kubectl context, run `kubectl config use-context <my-context>`


#### Minikube
Minikube sets up a context for kubectl when you set it up. To use it, just run:
```shell script
kubectl config use-context minikube
```

#### Google Kubernetes Engine
GCloud can automatically configure the kubectl context for your cluster: 

```shell script
GCP_CLUSTER=gedi-cluster-prod
GCP_PROJECT=us-east1-b
GCP_ZONE=jax-gedi-sandbox-nc-01
gcloud container clusters get-credentials $GCP_CLUSTER --zone $GCP_ZONE --project $GCP_PROJECT
```

If you had already created a context and since changed it to point to a different cluster, simply run:
```shell script
kubectl config use-context gke_$GCP_PROJECT\_$GCP_ZONE\_$GCP_CLUSTER
```

### Finding your pod
Find a pod running your service. It's going to use the kebab-case application name, followed by a unique id.
```shell script
kubectl get pods
```
```shell script
NAME                                         READY   STATUS   RESTARTS   AGE
project-kebab-755f4c8f69-gmkt8   0/1     Error    2          32s
```

### Inspecting pod logs
Then, inspect the logs of your running container:
```shell script
POD=project-kebab-755f4c8f69-gmkt8
kubectl logs $POD
```
We can immediately see that I forgot to provide a secret key.
```shell script
[project-kebab-755f4c8f69-gmkt8 project-kebab] [2020-04-30 17:21:33 +0000] [16] [ERROR] Exception in worker process
[project-kebab-755f4c8f69-gmkt8 project-kebab] Traceback (most recent call last):
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/arbiter.py", line 583, in spawn_worker
[project-kebab-755f4c8f69-gmkt8 project-kebab]     worker.init_process()
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/workers/gthread.py", line 92, in init_process
[project-kebab-755f4c8f69-gmkt8 project-kebab]     super().init_process()
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/workers/base.py", line 133, in init_process
[project-kebab-755f4c8f69-gmkt8 project-kebab]     self.load_wsgi()
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/workers/base.py", line 142, in load_wsgi
[project-kebab-755f4c8f69-gmkt8 project-kebab]     self.wsgi = self.app.wsgi()
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/app/base.py", line 67, in wsgi
[project-kebab-755f4c8f69-gmkt8 project-kebab]     self.callable = self.load()
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/app/wsgiapp.py", line 49, in load
[project-kebab-755f4c8f69-gmkt8 project-kebab]     return self.load_wsgiapp()
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/app/wsgiapp.py", line 39, in load_wsgiapp
[project-kebab-755f4c8f69-gmkt8 project-kebab]     return util.import_app(self.app_uri)
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/gunicorn/util.py", line 331, in import_app
[project-kebab-755f4c8f69-gmkt8 project-kebab]     mod = importlib.import_module(module)
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/lib/python3.7/importlib/__init__.py", line 127, in import_module
[project-kebab-755f4c8f69-gmkt8 project-kebab]     return _bootstrap._gcd_import(name[level:], package, level)
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "<frozen importlib._bootstrap>", line 1006, in _gcd_import
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "<frozen importlib._bootstrap>", line 983, in _find_and_load
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "<frozen importlib._bootstrap>", line 967, in _find_and_load_unlocked
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "<frozen importlib._bootstrap>", line 677, in _load_unlocked
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "<frozen importlib._bootstrap_external>", line 728, in exec_module
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "<frozen importlib._bootstrap>", line 219, in _call_with_frames_removed
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/opt/project_snake/app.py", line 8, in <module>
[project-kebab-755f4c8f69-gmkt8 project-kebab]     import config
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/opt/project_snake/config.py", line 65, in <module>
[project-kebab-755f4c8f69-gmkt8 project-kebab]     SECRET_KEY = env.str('SECRET_KEY')
[project-kebab-755f4c8f69-gmkt8 project-kebab]   File "/usr/local/bin/venv.project_snake/lib/python3.7/site-packages/environs/__init__.py", line 75, in method
[project-kebab-755f4c8f69-gmkt8 project-kebab]     raise EnvValidationError('Environment variable "{}" not set'.format(source_key), [message])
[project-kebab-755f4c8f69-gmkt8 project-kebab] environs.EnvValidationError: Environment variable "SECRET_KEY" not set
[project-kebab-755f4c8f69-gmkt8 project-kebab] [2020-04-30 17:21:33 +0000] [16] [INFO] Worker exiting (pid: 16)
[project-kebab-755f4c8f69-gmkt8 project-kebab] [2020-04-30 17:21:33 +0000] [11] [INFO] Shutting down: Master
[project-kebab-755f4c8f69-gmkt8 project-kebab] [2020-04-30 17:21:33 +0000] [11] [INFO] Reason: Worker failed to boot.

```
To fix it, provide a secret for the app
```shell script
SECRETS_FILE="deploy/secrets.local.txt"
touch $SECRETS_FILE
echo "SECRET_KEY='Z\xad\xad\\a\xd5w\xc2\xf6(\x08\x03\x0b\` \xe5\x16m\xa9\xc8'" >> $SECRETS_FILE
kubectl create secret generic "project-kebab-testing-secrets" --from-env-file="$SECRETS_FILE"
```

### Gain Access to a Running Pod
To get access to a pod that's currently running in kubernetes, run:
```shell script
IMAGE=$project-kebab
kubectl exec -it $POD $IMAGE
```

Since this application only has one image per pod, we can actually leave off the $IMAGE
```shell script
kubectl exec -it $POD
```

-----
<sub>Created from the [deploy cookiecutter template](https://bitbucket.jax.org/projects/PT/repos/deploy/browse) on Wed, Dec 16 2020 at 16:18 PM</sub>

<sub>This code is maintained by alexander.berger@jax.org. The template was created by alexander.berger@jax.org</sub>