---
title: Smart Road — ASTM D6433 PCI
emoji: 🛣️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Grades a road to ASTM D6433 from a photograph or drive video
---

# Smart Road

Upload a photograph of a road surface or a short drive video. The app detects
pavement distresses, converts them into square metres on the road plane by
inverse perspective mapping, and runs them through ASTM D6433 to produce a
Pavement Condition Index from 0 to 100 — with the full deduct chain that
produced it.

Weights are fetched from
[uzbtrust/smart-road-pci-yolo11](https://huggingface.co/uzbtrust/smart-road-pci-yolo11)
on first use.

**This Space runs on CPU.** A single photograph takes a few seconds; the video
mode samples one frame per second and will be noticeably slower than the
figures quoted in the repository, which were measured on Apple Silicon.

Source, dataset and validation:
[github.com/uzbtrust/smart-road](https://github.com/uzbtrust/smart-road)

Code MIT. Weights AGPL-3.0, inherited from Ultralytics YOLO11.
