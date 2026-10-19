# GaaS guide review and corrected launch preparation

Source: the user-uploaded `../gaas.pdf`, preserved unchanged. PDF text was extracted with the existing Ghostscript utility into `gaas-guide.txt`; no package was installed. The user's project code is `fs_ccds_asysong`.

| Setting | Evidence and decision |
|---|---|
| Submission queue | PDF pp. 7–8: `gpu_free`. Live `qstat -Qf` confirms it is a routing queue. Updated site config and all seven prepared commands. |
| Execution queues | `gpu_free_high` and `gpu_free_normal` both require routed submissions. The previous direct-normal commands were incorrect for the current scheduler. |
| Project access | User confirmed `fs_ccds_asysong`; `id -Gn` gives `hpc_fs_asysong_group`, present in both free execution-queue ACLs. No billing/submission was performed. |
| GPU type | PDF pp. 7–8: eight H200s on `hpc-gaas-g25`. Live node metadata assigns that node to `Qlist=gpu_free`. Retain allocated GPU name/memory validation; no host or undocumented selector is added. |
| Resources | Retain one GPU, 12 CPUs, 64 GB. The current `/usr/local/templates/submit_gpu_test.pbs` recommends 12 CPUs per GPU; the older general guide examples use four. |
| Walltime | PDF: four hours. Live normal queue: six hours; high: one hour. Keep the existing two-hour request, within the published four-hour limit. Do not assume the longer advertised limit supersedes policy. |
| Modules | Existing observed `pytorch/2.11.0` remains selected; no speculative module change. |
| Datamover | PDF pp. 8, 12: `gpu_datamover`, dm1/dm2. Live maximum: four CPUs, zero GPUs, 120 hours. Site datamover example uses four CPUs and rsync; its unrelated project/path commands were not copied or run. |
| Downloads | The linked detailed datamover guide is absent from this PDF. External PyPI/Hugging Face egress/proxy details remain unconfirmed; `download_policy_confirmed` stays false. |
| Login node | PDF p. 3 prohibits workloads. Further test suites, builds, inference and training should run in allocations. This review used file inspection, scheduler queries and command rendering only. |

Changed files: `configs/pbs_site.example.yaml`, `scripts/pbs_launch.py` (status text), `README.md`, audit evidence and regenerated `submission-commands.txt`. The original implementation report is retained with a superseding site-update note.

Validation: all seven rendered commands use `-q gpu_free -P fs_ccds_asysong`; the launcher parses successfully; original project-file hashes and uploaded PDF hash match. No workload test suite was rerun on the login node, no package/model download occurred, and no job was submitted.

Next: prepare dependencies and pinned model files through an approved datamover transfer route, then run the allocated preflight and the 36-presentation pilot. GPU submission still requires the separate authorization specified in the original request.
