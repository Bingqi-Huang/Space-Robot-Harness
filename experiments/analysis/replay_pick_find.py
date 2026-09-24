"""Replay every pick's find stage of the scripted chains offline from its recorded frame (K, camera pose, declared
work point, yaw, handle) against the current interface fit; prints live vs replayed agreement. Run with openral's
venv inside the run-farm image (pinned to the host cores)."""
import json, glob, math, os, numpy as np
from openral_rskill import interface_fit as F
R='/mnt/SharedData/Research/Space_Robot_Harness/'
ix=json.load(open(R+'space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json'))
for log in sorted(glob.glob(R+'artifacts/runs/chain_*_f/capability_server.log')):
    for line in open(log):
        if 'CAPABILITY {' not in line or '"pick"' not in line: continue
        d=json.loads(line[line.index('{'):]); f=d['evidence'].get('skill',{}).get('find',{})
        if 'view' not in f or 'K' not in f['view'] or not f.get('fit'): continue
        K=np.array(f['view']['K']); T=np.array(f['view']['T_base_cam'])
        ddir=os.path.dirname(f['view']['image']); depth=np.load(ddir+'/view_depth.npy').astype(np.float32)
        dims=d['evidence']['goal']['held_item']['interface']; up=T[:3,:3].T@np.array([0,0,1.0])
        bp=d['evidence']['base_pose']; sp=np.array(ix['points'][d['args']['support']]['xyz'])
        c,s=math.cos(bp['yaw']),math.sin(bp['yaw']); rel=sp[:2]-[bp['x'],bp['y']]
        at=np.array([c*rel[0]+s*rel[1],-s*rel[0]+c*rel[1],d['args']['grasp_height_m']])
        hint=T[:3,:3].T@(at-T[:3,3]); yaw=f['fit']['yaw_rad']
        new=F.locate(depth,K,dims,up,yaw,f['tool_in_view']['self_depth_m'],hint)
        print(log.split('/')[-2][6:], d['args']['support'][:22].ljust(22), 'live', 'OK ' if d['success'] else 'FAIL', 'agree', f['fit']['agreement'], 'xyz', [round(v,3) for v in f['fit']['xyz_cam']], '| new agree', round(new.agreement,3), 'xyz', [round(float(v),3) for v in new.xyz_cam])
