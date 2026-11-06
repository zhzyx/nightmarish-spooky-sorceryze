# Local motion providers

The standard-library `motion_provider.py` implements the existing `NodeRegistry` /
`Provider` protocol, including durable invocation identity and immutable results.
`factory()` reads trusted `AINATIVE_MOTION_CONFIG` and works with `Executor`.
The motion panel invokes this bridge; model dependencies only load in the
configured independent Python subprocess. A future provider can be selected by
trusted `provider_factory` / `provider_id` configuration without changing the UI.

Create a **separate** Python 3.12 environment under an ignored `runtime/motion`,
install `motion-requirements.txt`, and install OpenAI CLIP from its official Git
repository at `d05afc436d78f1c48dc0dbf8e5980a9d471f35f6`. Keep its MIT notice.
Do not install into an image/mesh provider environment.

Required local assets (all paths below relative to the runtime):

| Path | Official source / version |
| --- | --- |
| `mdm/` | https://github.com/GuyTevet/motion-diffusion-model at `ef8edce6a53c6ab19e53b4d4dcf15bc0bc60a778`, MIT |
| `models/humanml_enc_512_50steps/` | Extract official README Google Drive checkpoint `1cfadR1eZ116TIdXK7qDX1RugAerEiJXr` |
| `humanml/HumanML3D/{Mean,Std}.npy` | https://github.com/EricGuo5513/HumanML3D at `9176e8fb446b71c7d2a725eb5cf6fec1ae3b3c23`, repository MIT |
| `models/ViT-B-32.pt` | Official OpenAI CLIP `ViT-B/32`, SHA `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af` |
| `models/pose.task` | `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task` |
| `models/hand.task` | `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task` |
| `models/face.task` | `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` |

Download weights to a temporary name, verify complete content, then move into
place. CLIP inference refuses incomplete/unverified weights. Keep all upstream
notices and model cards; no weights, private videos or licensed UE assets belong
in the repository. Source/model/input SHA values accompany inference output.

Copy `motion-config.example.json` to the private runtime `config.json`, configure
absolute paths, then run with a standard Python interpreter:

```powershell
python tools/ainative/motion_provider.py --config runtime/motion/config.json --mode text_to_motion --prompt "A person walks forward and raises both arms." --context "The movement is slow and deliberate." --output runtime/motion/new-text-version.json
python tools/ainative/motion_provider.py --config runtime/motion/config.json --mode video_to_motion --video LOCAL_VIDEO --output runtime/motion/new-video-version.json
```

Every destination must be new. Repeated identical submissions reuse the durable
provider receipt and never silently overwrite a version. Independent workers
hold exclusive job locks; OS PID plus creation identity prevents PID reuse from
being mistaken for progress. Complete raw results can reconstruct a missing
manifest/receipt without rerunning inference. Unknown interrupted launches raise
`reconciliation_required`; inspect their local log instead of pretending they
are still running or automatically resubmitting. The CLI polls asynchronous
`queued`/`running` receipts. This first local adapter does not promise remote
cancellation; active jobs finish under their existing identity.

Open the workbench's **Motion generation** section. Enter runtime, action or
local video, context and new output path. Load/preview creates an explicit source
Profile before retargeting. Use a #147 target Profile, or an actual bound avatar
plus its skeleton family. The timeline scrubs the real AnimationPlayer. Saving
publishes an immutable `.tscn` containing animation, both Profile identities,
raw body/hand/face streams, correction history and processing diagnostics.

Point edits use JSON, for example
`[{"stream":"body","frame":2,"point":31,"position":[0,0.7,0]}]`.
Coordinates remain in that stream's documented source coordinate system. Edits
retain `raw_positions`, original confidence and grouped observations. Low
visibility and missing frame times are displayed. Temporal smoothing is explicit;
retarget fps and planted contact intervals reuse #147's implementation. Reported
contact residuals and loop seams must be inspected; loop mode does not synthesize
a seamless loop.

Text ContextBundle entries feed the real CLIP prompt and retain consumption and
origin-version records. Image conditioning is unsupported and rejected by the
node contract. Video text context is explicitly metadata only, not a pose model
condition. MDM emits 22 body joints at 20 Hz, no finger/face animation. MediaPipe
keeps body, hand and face clocks and units separate; handedness scores and face
coefficients are **not** joint confidence. Missing confidence stays null.
Single-person selection is not persistent multi-person tracking. Hip-relative
monocular body coordinates do not recover absolute root travel. Position-only
body fitting cannot recover axial twist. Facial binding is deferred to #151.

Contract tests run with `python -m unittest discover -s tools/ainative`.
`motion_acceptance.gd` validates actual inference documents in headless Godot;
`motion_live_ui.gd` uses a private config to replay target meshes, publish/reopen
versions and capture two times plus the actual motion controls. Synthetic unit
fixtures are not inference acceptance evidence.
