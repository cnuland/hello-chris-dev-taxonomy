# Quick reference: Argo direct path for InstructLab

- Create RBAC
  kubectl apply -f rbac-argo-workflow.yaml

- Sanity check
  kubectl apply -f wf-check.yaml
  kubectl -n petloan-instructlab get workflow ilab-storage-sched-check -o jsonpath='{.status.phase}\n'

- Launch pipeline
  kubectl create -f instructlab-argo-workflow.yaml

- Monitor
  kubectl -n petloan-instructlab get pods -l workflows.argoproj.io/workflow=<workflow>
  kubectl -n petloan-instructlab get workflow <workflow> -o jsonpath='{.status.phase} {.status.message}\n'

- Cleanup a workflow
  kubectl -n petloan-instructlab delete workflow <workflow>

Notes
- Early tasks run on CPU. Training tasks request GPU with toleration for nvidia.com/gpu taint and nodeSelector nvidia.com/gpu.present=true. Adjust if your cluster uses different labels/taints.
- PVCs use gp3 RWO. Sizes are 50Gi (data), 50Gi (model-cache), 100Gi (output); edit instructlab-argo-workflow.yaml to change.

