# DonkeyCar × modern ML — a build roadmap

A staged plan for combining a DonkeyCar (Jetson Nano + Coral Edge TPU stick) with
recent advances in RL, LLMs, and VLAs. Phases run **most feasible → most
ambitious**; each reuses the deployment pipeline built in the phase before it.
Start with Phase 0 — the hardware audit decides what is even possible.

---

## The one architectural idea

Everything below is a variation on a three-tier split:

- **System 1 — Coral Edge TPU:** a tiny INT8 conv+MLP policy at high FPS, low power. The real-time control/perception loop lives here.
- **Host — Jetson Nano:** camera I/O, the Coral USB host, light glue. On the original Nano it does little else.
- **System 2 — off-board GPU (laptop/cloud):** the heavy, slow, "smart" model (VLA / LLM planner) at 1–3 Hz over wifi. Optional, added late.

Hard truth that shapes the whole plan: **train off-device, deploy on-device.**
The original Nano's software stack is too old to run a modern training stack
(see Phase 0), and the Coral is INT8-inference-only. So all learning happens on
your laptop/cloud; the car only ever runs a compiled artifact.

---

## Phase 0 — Hardware audit & known-good baseline *(prerequisite, low effort)*

**Goal:** know exactly what stack each device runs, and get the stock pipeline working end to end before adding any ML.

- Run every check in the [Compatibility checks](#compatibility-checks) section and write the results into a short `HARDWARE.md`.
- Get the stock DonkeyCar install driving via teleop; confirm the camera and PWM.
- Run the Coral reference model (MobileNet bird classifier) to prove the USB chain + runtime work, and record a latency baseline.

**Milestone:** a filled-in `HARDWARE.md` and a working teleop loop + a Coral that returns inferences.
**Risk:** this is where you discover an original Nano is stuck on Ubuntu 18.04 / Python 3.6 / CUDA 10.2. Better to know now.

---

## Phase 1 — Line following, the easy way: classic CV, no ML *(most feasible — a weekend)*

**Goal:** get the car physically driving a loop and set a lap-time *baseline to beat*. No neural net.

- Lay down a line (tape on the floor) and point the camera **forward, not at the ground** — looking ahead is the whole advantage of a camera over a Lego-style reflectance sensor, and it's what lets later versions anticipate corners and brake into them.
- Threshold the image, find the line's centroid, steer proportional to its offset (a plain P-controller). ~30 lines of OpenCV, runs on the Nano's CPU.
- Time a clean lap. That number is the benchmark for everything below.

**Why bother, when a Lego robot can do this:** the point isn't the task, it's commissioning the physical loop (camera → compute → PWM → motion) and its latency/actuation on a problem you *know* is winnable. If the car can't follow a taped line, the bug is in your plumbing, not your model. This is the "known-good baseline" half of Phase 0, made to actually drive.
**Milestone:** the car drives the loop unaided; you have a baseline lap time.
**Risk:** shadows/lighting breaking a fixed threshold — note where it fails; that's exactly what the learned version fixes.

---

## Phase 2 — Line following, the learned way: BC-CNN → Coral *(feasible, foundational)*

**Goal:** redo Phase 1 as a learned policy — purely to **commission the train → quantize → compile → deploy pipeline** that every later phase reuses — and try to beat the CV lap time.

- Collect data by letting the Phase-1 CV controller drive while you log frames + its steering/throttle (free labels), and/or teleop. Train the classic Donkey CNN (a few conv layers → dense → steering/throttle) on your laptop.
- Full-INT8 quantize (prefer **quantization-aware training** — keeps the accuracy drop ~1%), then `edgetpu_compiler` on an x86 box, then run on the Coral.
- Keep the net **conv+MLP, ReLU6, fixed input size** — no LSTM/attention (those fall back to CPU on the Edge TPU).
- **The payoff:** because the policy sees *ahead*, it can carry more speed through corners and modulate throttle — so the real test is whether the learned lap beats the reactive CV baseline. The moment it does, the whole stack is justified.

**Recent-advance hook:** the modern export path (`ai-edge-torch` for PyTorch→TFLite, or `jax2tf`→TFLite), then LiteRT + the `libedgetpu` delegate instead of the stale PyCoral.
**Milestone:** a Coral-compiled CNN drives the loop with ~100% of ops mapped to the TPU (check the compile log), ideally a faster lap than Phase 1.
**Risk:** op-support surprises in the compile log; a fixed-shape camera pre-process. The same pipeline generalizes to full-track driving later — the line is just the first task.

---

## Phase 3 — LLM as an offline copilot *(feasible, runs in parallel)*

**Goal:** use a big off-board LLM where latency is irrelevant — never in the control loop.

- Auto-write and iterate **reward functions** for later RL (Eureka-style search).
- Generate **track curricula** and scenario variations.
- **Failure post-mortems:** feed telemetry logs and ask why it understeered into turn 3.

**Compute:** entirely off-board, offline. Zero on-device cost.
**Milestone:** a reward/curriculum generator script and a log-analysis prompt you actually reuse.
**Risk:** low — mostly prompt and harness plumbing.

---

## Phase 4 — Sim RL with PufferLib (Python, no C) → distil to Coral *(moderate)*

**Goal:** learn a driving policy in simulation without hand-labelled data, using a clean fast PPO.

- Wrap `gym-donkeycar` with PufferLib and train with **PuffeRL**; you write only Python. (C is needed *only* to author native Ocean envs — not to use the library.)
- Use **Protein** (PufferLib's auto hyperparameter/reward tuner) to avoid hand-tuning.
- Apply **domain randomization** (lighting, textures, dynamics), then distil the policy to a small conv+MLP and push it through the Phase-2 pipeline to the Coral.

**Reality check:** `gym-donkeycar` is a Unity sim over a socket, so it sits in PufferLib's *slow* tier — you get a solid PPO and tuning, not the millions-of-steps/s headline (the sim is the bottleneck).
**Milestone:** a sim-trained policy that completes a real lap after sim2real distillation.
**Risk:** the sim2real gap; reward shaping.

---

## Phase 5 — High-throughput custom env (JAX *or* Ocean C) → distil to Coral *(more ambitious)*

**Goal:** unlock fast RL by removing the simulator bottleneck.

- Write a tiny top-down 2D driving env (kinematic bicycle model, track centerline, a few range-sensor rays or a downsampled cam). ~200–400 lines.
- **Path A (your JAX wheelhouse):** implement it in JAX, vectorize thousands of envs on the GPU, train PureJaxRL-style — no C at all.
- **Path B (learn a little C):** write it as a PufferLib **Ocean** env for 1M+ steps/s; the community reviews env PRs live and an LLM can scaffold the C.
- Train with heavy domain randomization → distil → INT8 → Coral.

**Milestone:** "train a competent policy in minutes," then transfer it to the car.
**Risk:** building a faithful-enough toy env; transfer still needs DR.

---

## Phase 6 — LeRobot data platform + SmolVLA fine-tune *(ambitious, publishable)*

**Goal:** plug the car into the open robotics ecosystem.

- Log teleop + autonomous runs in **LeRobot dataset format**; publish the dataset.
- Fine-tune **SmolVLA** (≈450M, runs on consumer hardware) on your track; recent work shows useful in-context adaptation from ~20 demos.

**Compute:** data collection on the car; training off-board; inference off-board (or on an Orin-class device).
**Milestone:** a published dataset + a fine-tuned checkpoint and a short write-up.
**Risk:** data quality/coverage; SmolVLA won't run on the original Nano (off-board only).

---

## Phase 7 — Dual-system "talk to your car" *(ambitious, best demo)*

**Goal:** language-conditioned driving with a slow brain + fast reflexes.

- Off-board **system 2** (SmolVLA / a VLM planner) consumes the camera stream and emits high-level intent at 1–3 Hz over a websocket.
- On-board **system 1** (the Coral policy from Phase 2/4/5) tracks that intent at 20–30 Hz and owns safety.
- Handle the async perception/action split and the wifi latency budget explicitly (this is the interesting part — it mirrors Helix/GR00T dual-system designs).

**Milestone:** "hug the left line, stop at the cone" works, spoken aloud.
**Risk:** latency/jitter; safe fallback when the link drops.

---

## Phase 8 — Dream-to-drive: a JAX world model *(most ambitious, research-grade)*

**Goal:** model-based RL for sample efficiency — learn a latent world model, train the policy in imagination, deploy a distilled actor.

- Learn the world model from logged driving; train the actor in imagination (Dreamer-style).
- Ship only the tiny actor to the Coral; the world model stays off-board.

**Milestone:** a policy trained largely in imagination that drives the real track.
**Risk:** the hardest of the set; world-model fidelity and stability.

---

## Suggested sequence

Phases 0 → 2 are the backbone; do them first. Phase 3 (the LLM copilot) can run
anytime in parallel. Then 4 → 5 build the RL muscle, 6 → 7 add the language/VLA
layer, and 8 is the stretch goal. A good first two weekends: **Phase 0 audit +
Phase 1 CV line-follower** (get it physically driving, set a lap time), then
**Phase 2 BC-CNN → Coral** (commission the deploy pipeline and try to beat that
lap time) — after which you have a pipeline every later phase plugs into.

---

## Compatibility checks

Run these first (Phase 0). The headline question is **which Jetson you have** —
an *original* Nano (Maxwell, 4 GB) and an *Orin* Nano (Ampere, 8 GB) are worlds
apart for a modern stack.

### Jetson

| Check | Command | What good looks like / red flag |
|---|---|---|
| **Which board** | `cat /proc/device-tree/model` | "Orin Nano" → modern stack OK. Plain "Jetson Nano" → expect the old stack below. |
| L4T / JetPack | `head -n1 /etc/nv_tegra_release` | Original Nano: `R32` (JetPack 4.6, EOL). Orin: `R35`/`R36` (JetPack 5/6). |
| OS | `cat /etc/os-release` | Nano: Ubuntu **18.04**. Orin: 20.04/22.04. 18.04 blocks most modern wheels. |
| Python | `python3 --version` | Nano: **3.6** (red flag — modern libs need ≥3.9). Orin: 3.8/3.10. |
| CUDA | `cat /usr/local/cuda/version.txt` or `nvcc --version` | Nano: **10.2** (red flag). Orin: 11.4/12.x. |
| GPU compute capability | `deviceQuery` or `python3 -c "import torch;print(torch.cuda.get_device_capability())"` | Nano: **(5,3)** Maxwell — many wheels need ≥7.0. Orin: (8,7). |
| PyTorch | `python3 -c "import torch;print(torch.__version__,torch.cuda.is_available())"` | Use NVIDIA's Jetson wheels. Nano caps ~torch 1.13. |
| TensorRT | `python3 -c "import tensorrt;print(tensorrt.__version__)"` | Present and importable; this is your real on-device inference runtime. |
| RAM / swap | `free -h` && `swapon --show` | 4 GB on Nano → add zram/swap, run headless. |
| Power mode | `sudo nvpmodel -q` && `sudo jetson_clocks --show` | Set max-perf mode (`nvpmodel -m 0`) + `jetson_clocks` before benchmarking. |
| Monitoring | `sudo pip3 install -U jetson-stats` then `jtop` | Live GPU/CPU/thermal/power. |
| USB for Coral | `lsusb -t` | Coral on a **5000M** (USB 3.0) port. USB 2.0 throttles it badly. |
| Camera | `ls /dev/video*` | Camera enumerates; test a GStreamer pipeline. |

**Verdict to record:** if it's an original Nano (18.04 / Py3.6 / CUDA 10.2), do
**all training off-device** and treat the Nano as a TensorRT-engine runner + Coral
host. Don't fight to put JAX/modern-PyTorch/PufferLib on it. If it's an Orin Nano,
on-device small VLM/LLM work (e.g. 4-bit Qwen-class via TensorRT-LLM) becomes
viable and Phases 5–6 can partly move on-device.

### Coral Edge TPU (USB)

| Check | Command | What good looks like / red flag |
|---|---|---|
| Device present | `lsusb \| grep -iE 'Global Unichip\|Google'` | `1a6e:089a` (Global Unichip) before first use; `18d1:9302` (Google) after init. |
| USB 3.0 | `lsusb -t` | Shows **5000M** for the Coral. On USB 2.0 it runs but much slower. |
| Runtime | `dpkg -l \| grep libedgetpu` | `libedgetpu1-std` (cooler) or `-max` (faster/hotter). Present = good. |
| TPU visible to API | `python3 -c "from pycoral.utils import edgetpu; print(edgetpu.list_edge_tpus())"` | Returns a non-empty list. |
| Python binding | `python3 -c "import tflite_runtime, pycoral"` | Imports cleanly. **Red flag:** PyCoral has no wheel for your Python → use **LiteRT (`ai-edge-litert`) + the `libedgetpu.so.1` delegate** instead (the maintained path). |
| Reference model | run PyCoral `classify_image.py` with the MobileNet bird model | A correct label + a few-ms repeat latency = whole chain works. |
| Compiler (on **x86**, not the Nano) | `edgetpu_compiler --version` | The compiler is x86-only; you need a Linux PC or Colab to compile. |
| Op coverage | read the `edgetpu_compiler` log after compiling your model | "Mapped to Edge TPU" should be ≈ all ops; lots of "Mapped to CPU" = redesign (avoid LSTM/h-swish/dynamic shapes). |
| Thermal | touch-test / `jtop` after sustained inference | The stick throttles when hot; budget airflow for long runs. |

**Verdict to record:** confirm (a) the Coral runs the reference model from your
*actual* Nano OS/Python, (b) you have an x86 machine for `edgetpu_compiler`, and
(c) a trivial conv+MLP compiles to ~100% on-TPU. If PyCoral won't install on your
Python, standardize on LiteRT + the libedgetpu delegate now — it saves pain later.

---

## Key references

- DonkeyCar: <https://docs.donkeycar.com> · gym-donkeycar: <https://github.com/tawnkramer/gym-donkeycar>
- VAE+SAC "learn to drive": <https://github.com/araffin/aae-train-donkeycar>
- PufferLib: <https://puffer.ai/docs.html> · PufferLib 2.0 paper (OpenReview): <https://openreview.net/pdf?id=qRyteMTgn0>
- JAX RL: Brax, MJX (MuJoCo), PureJaxRL, gymnax
- SmolVLA / LeRobot: <https://github.com/huggingface/lerobot>
- Coral Edge TPU models & constraints: <https://www.coral.ai/docs/edgetpu/models-intro> · compiler: <https://www.coral.ai/docs/edgetpu/compiler>
- LiteRT / PyTorch→TFLite: `ai-edge-torch`, `ai-edge-litert`
