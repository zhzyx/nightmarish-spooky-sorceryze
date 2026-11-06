"""Adapter to official MDM inference. No action lookup or prerecorded motion."""
import argparse
import json
import os
from pathlib import Path
import sys
from motion import digest, publish, text_context


def run(args):
    import numpy as np
    import torch
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    import clip
    original_clip_load = clip.load
    clip_file = repo.parent / 'models/ViT-B-32.pt'
    if not clip_file.is_file() or digest(clip_file) != '40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af':
        raise ValueError('Complete verified official CLIP ViT-B-32.pt download required before inference')
    clip.load = lambda *a, **kw: original_clip_load(*a, **dict(kw, download_root=str(repo.parent / 'models')))
    # Official MDM constructs SMPL even for hml_vec, although hml_vec inference
    # never invokes it. Remove only this unused conversion in the loaded module;
    # preserve the entire neural network and official checkpoint loading.
    import types
    source = (repo / 'model/mdm.py').read_text()
    source = source.replace('from model.rotation2xyz import Rotation2xyz', '')
    source = source.replace("self.rot2xyz = Rotation2xyz(device='cpu', dataset=self.dataset)", "self.rot2xyz = None\n        assert self.data_rep == 'hml_vec', 'Only HumanML3D vectors are supported'")
    source = source.replace('self.rot2xyz.smpl_model._apply(fn)', 'pass')
    source = source.replace('self.rot2xyz.smpl_model.train(*args, **kwargs)', 'pass')
    module = types.ModuleType('model.mdm')
    sys.modules['model.mdm'] = module
    exec(compile(source, str(repo / 'model/mdm.py'), 'exec'), module.__dict__)
    from utils.parser_util import add_base_options, add_data_options, add_model_options, add_diffusion_options
    from utils.model_util import create_model_and_diffusion, load_saved_model
    from utils.sampler_util import ClassifierFreeSampleModel
    from data_loaders.humanml.scripts.motion_process import recover_from_ric
    parser = argparse.ArgumentParser()
    for add in [add_base_options, add_data_options, add_model_options, add_diffusion_options]:
        add(parser)
    config = parser.parse_args([])
    vars(config).update(json.loads(Path(args.checkpoint).with_name('args.json').read_text()))
    if config.dataset != 'humanml':
        raise ValueError('Only HumanML3D checkpoint supported')
    model, diffusion = create_model_and_diffusion(config, types.SimpleNamespace(dataset=types.SimpleNamespace()))
    load_saved_model(model, args.checkpoint, use_avg=True)
    model = ClassifierFreeSampleModel(model).to(args.device).eval()
    count = round(args.seconds * 20)
    if not 1 <= count <= 196:
        raise ValueError('Duration must be 0.05..9.8 seconds')
    prompt = args.prompt + ('\nContext: ' + args.context if args.context else '')
    y = {'text': [prompt], 'lengths': torch.tensor([count], device=args.device), 'mask': torch.ones(1, 1, 1, count, dtype=torch.bool, device=args.device), 'scale': torch.tensor([2.5], device=args.device)}
    with torch.no_grad():
        y['text_embed'] = model.encode_text(y['text'])
        sample = diffusion.p_sample_loop(model, (1, 263, 1, count), clip_denoised=False, model_kwargs={'y': y}, progress=True)
        mean = torch.tensor(np.load(args.mean), device=args.device)
        std = torch.tensor(np.load(args.std), device=args.device)
        vectors = sample.permute(0, 2, 3, 1) * std + mean
        positions = recover_from_ric(vectors, 22)[0, 0].cpu().numpy()
    frames = [{'timestamp_ms': i * 50, 'positions': points.tolist(), 'confidence': None, 'confidence_note': 'Generative model does not expose calibrated joint confidence', 'missing': False} for i, points in enumerate(positions)]
    doc = {'schema': 'ainative.motion.v1', 'fps': 20, 'source_profile': {'id': 'humanml3d-22-v1', 'root_motion': 'model_generated', 'units': 'meters', 'up': '+Y'}, 'provenance': {'provider': 'official-MDM', 'source': 'https://github.com/GuyTevet/motion-diffusion-model', 'source_sha256': digest(repo / 'model/mdm.py'), 'checkpoint_sha256': digest(args.checkpoint), 'mean_sha256': digest(args.mean), 'std_sha256': digest(args.std), 'seed': args.seed, 'device': args.device, 'steps': config.diffusion_steps, 'prompt': prompt, 'unused_smpl_conversion': 'excluded for hml_vec only'}, 'streams': {'body': {'time_base': 'model_20fps_ms', 'coordinate_system': 'humanml3d_meters', 'frames': frames}, 'hands': {'time_base': 'model_20fps_ms', 'frames': [], 'missing_reason': 'Model has wrists but no fingers'}, 'face': {'time_base': 'model_20fps_ms', 'frames': [], 'missing_reason': 'Model has no face stream'}}}
    doc['context'] = text_context(args.context, True)
    doc['provenance']['clip_sha256'] = digest(clip_file)
    doc['provenance']['checkpoint_arguments_sha256'] = digest(Path(args.checkpoint).with_name('args.json'))
    doc['provenance']['adapter_sha256'] = digest(__file__)
    doc['capabilities'] = {'image_context': 'unsupported; rejected at interface', 'text_context': 'CLIP prompt conditioning'}
    return publish(doc, args.output)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ['repo', 'checkpoint', 'mean', 'std', 'prompt', 'output']:
        p.add_argument('--' + key, required=True)
    p.add_argument('--context', default='')
    p.add_argument('--device', default='cpu')
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--seed', type=int, default=10)
    p.add_argument('--seconds', type=float, default=4)
    print(json.dumps({'revision': run(p.parse_args())}))
