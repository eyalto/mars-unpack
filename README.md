# mars-unpack
unpack and organize input data 


flask app --> redis (work queue)
                ^
                |__________
                          |
                          v
                       consumer
                          
how to debug:

follow this post https://betterprogramming.pub/remote-interactive-debugging-of-python-applications-running-in-kubernetes-17a3d2eed86f

added labels to deployment.yaml in the helm template to allow the selector to output the pod name

  template:
    metadata:
      {{- with .Values.podAnnotations }}
      annotations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      labels:
        {{- include "unpacker.selectorLabels" . | nindent 8 }}
        app: {{ .Values.nameOverride }}

getting pod name:
source the script get pod name in order to set the env cariable needed for the debug script to work 
source ./get_pod_names.sh

creating -> injecting the debug container into each debuggable pod
e.g.
./create-debug-container.sh default "$WEBAPP_POD" unpacker-app

execute the debugger 
kubectl exec "$WEBAPP_POD" --container=debugger -- python -m debugpy --listen 0.0.0.0:5678 --pid 1


port forward debugger port to local port each pod gets its own port (best to keep the same ports)