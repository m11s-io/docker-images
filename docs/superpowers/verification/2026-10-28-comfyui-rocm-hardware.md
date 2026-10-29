# ComfyUI ROCm hardware discovery — 2026-10-28

## Decision

The established Talos AMD host is accepted as the baseline per user clarification. Select ROCm 10.1.0 / PyTorch 2.14.0 / Python 3.14 from AMD's current documented image. The earlier 7.2.1/2.9.1 candidate is superseded. Topology inspection warnings are observations to compare with actual workload execution, not a host-support blocker.

## Observed target

Read-only kubectl discovery, explicitly targeting admin@plt:

- Node: plt-gpu-3, IP 10.10.17.59, amd64.
- Model label: accelerator.m11s.io/model=r9700. PCI devices: 0000:01:00.0 and 0000:02:00.0, both 1002:7551, subsystem 1458:242f, driver amdgpu.
- Each reports mem_info_vram_total=34208743424 bytes (31.86 GiB usable, consistent with nominal 32 GiB).
- Expected model: Radeon AI PRO R9700, RDNA4 / gfx1201 from node label and AMD specifications. Direct runtime marketing-name/gfx confirmation is pending: reads of GPU KFD topology name/properties return EPERM from both existing plugin and node-exporter containers.
- Talos v1.14.5, kernel 6.18.58-talos, containerd 2.3.7, Kubernetes 1.37.1.
- Talos amdgpu extension label: 20260916-v1.14.5. No separate /sys/module/amdgpu/version file; do not equate firmware extension version to AMD's packaged driver release.
- Allocatable: 5950m CPU, 13765836Ki RAM, amd.com/gpu=2. Requests already allocated: 2558m CPU, 1378Mi RAM, zero AMD GPUs. Approximately 3392m CPU and 11.78 GiB RAM remain by requests; this is not measured free memory.
- Taint tier.m11s.io=gpu:NoSchedule. Select accelerator.m11s.io/type=amd explicitly: this node also has a stale nvidia.com/gpu.present=true label.

## Device access and plugin

Read using existing read-only node-exporter host mounts:

- /dev/kfd: UID/GID 0:0, mode 0666, major/minor 236:0.
- /dev/dri/renderD128 and renderD129: UID/GID 0:0, mode 0666, major/minor 226:128 and 226:129.
- /dev/dri/card0 and card1: UID/GID 0:0, mode 0600.
- No supplemental group is indicated by compute-device mode bits alone. Non-root cgroup/device allocation and actual ROCm execution remain unverified.
- Device plugin: rocm/k8s-device-plugin:1.31.0.11, pinned digest e4df5dc9a7fa34e2344852256dcc5762171a6d68f1f9a34026ce26786ae335e2.
- Plugin registers two GPUs/render minors 128/129 despite topology read warnings, missing partition files, and P2P allocator initialization failure followed by kubelet-default allocation. KFD GPU topology reads return EPERM in both inspected containers. Root cause is not established; do not suppress warnings or relax security based on this observation alone.
- Available local Talos credential belongs to another cluster and fails TLS verification on this node. No bypass attempted.

## Selected image tuple

- Hardware: Radeon AI PRO R9700, RDNA4 / gfx1201, two nominal 32 GiB GPUs.
- ROCm 10.1.0, Ubuntu 26.04 userspace, Python 3.14, Linux amd64.
- Base: rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0@sha256:68295d40dcdcb53d9b50828f30017faad8cf5ad9a8c7923c5a815b414b45e3e6.
- Registry manifest and config inspected without pulling layers. Image history records torch[device-all]==2.14.0+rocm10.1.0, torchvision[device-all]==0.29.0a0+rocm10.1.0, torchaudio==2.11.0.3+rocm10.1.0 and rocm[devel,device-all]. The compressed base is approximately 11.8 GB; CI needs reclaimed runner disk space.
- Official wheel index: https://stable.repo.amd.com/rocm/whl-next/ . The digest-pinned image supplies the installed AMD wheel stack; CI checks its installed identities and constrains upstream installation. TorchVision's a0 version is AMD's matching documented build.
- PyTorch 2.15.0 released today, with ROCm 7.14 wheels observed. It is not substituted into the ROCm 10.1 tuple: AMD's current 10.1 validation lists 2.14.0, 2.13.0 and 2.12.0.

## Source compatibility

ComfyUI v0.43.0 requirements leave torch/torchvision unversioned, allowing the selected AMD builds under exact constraints. Its model_management.py has explicit HIP detection and gfx1201 handling. comfy-kitchen is pinned upstream to 0.2.40 and includes HIP, Triton and eager backends. The HIP source reports native extension loading separately from runtime GPU registration. CPU CI cannot establish which backend executes a model; hardware acceptance must record that separately.

Pinned ComfyUI-GGUF requirements are gguf>=0.13.0, sentencepiece and protobuf; GGUF operation/quantization compatibility is still a separate task and is not delivered in this generic-image change.

## Sources and remaining validation

- Current ROCm release notes, including R9700/gfx1201: https://rocm.docs.amd.com/en/latest/about/release-notes.html
- AMD current matrix: https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html
- Current AMD PyTorch images and pip instructions: https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html
- AMD GPU specs: https://rocm.docs.amd.com/en/latest/reference/gpu-specs.html
- ComfyUI source: https://github.com/Comfy-Org/ComfyUI/tree/v0.43.0
- Kitchen source: https://github.com/Comfy-Org/comfy-kitchen/tree/v0.2.40

No host driver, cluster setting, GPU label, PVC, or workload has been changed. Generic candidate build and CPU startup run in GitHub Actions; tensor/inference acceptance on the existing AMD host remains follow-up work. Existing security settings remain intact.
