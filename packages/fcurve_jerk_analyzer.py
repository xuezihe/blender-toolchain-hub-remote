# fcurve_jerk_analyzer.py
"""
@docs
F-Curve Jerk Analyzer for Blender Animation

This script analyzes animation F-Curves to detect the most jittery/unstable curves
around the current frame. It helps identify sudden changes, discontinuities, or
abnormal behavior in animation curves.

Usage:
1. Select an animated object in Blender
2. Move the timeline to the frame you want to analyze
3. Run this script in Blender's Python console or as a text script

Parameters (adjust at the top of the script):
- sample_offset: Number of frames to look before/after current frame (default: 1.0)
- top_n: Number of top jittery curves to display (default: 20)
- ignore_muted: Skip muted F-Curves (default: True)

Metrics calculated:
- swing: Total variation magnitude in the sampled window
- jerk: Second-order difference (acceleration change), detects sudden turns
- score: Weighted combination (jerk * 2.0 + swing), prioritizes abrupt jitter

Output:
Prints a ranked list of the most jittery F-Curves with their metrics,
group name, data path, and array index.
"""

import bpy
from math import fabs

obj = bpy.context.active_object
if obj is None:
    raise RuntimeError("没有激活对象")

ad = obj.animation_data
if ad is None or ad.action is None:
    raise RuntimeError("激活对象没有动画 Action")

action = ad.action
frame = bpy.context.scene.frame_current

# 可调参数
sample_offset = 1.0   # 看当前帧前后几帧，先用 1 帧最直观
top_n = 20            # 输出前多少条
ignore_muted = True   # 忽略 muted 曲线

results = []

for fc in action.fcurves:
    if ignore_muted and fc.mute:
        continue

    try:
        v_prev = fc.evaluate(frame - sample_offset)
        v_curr = fc.evaluate(frame)
        v_next = fc.evaluate(frame + sample_offset)
    except Exception:
        continue

    # 总摆动量：这一小段里变化有多大
    swing = fabs(v_curr - v_prev) + fabs(v_next - v_curr)

    # 局部“拐点/抖动”强度：越大越可能是接缝突然折一下
    jerk = fabs(v_next - 2.0 * v_curr + v_prev)

    # 综合分数：更偏向找“突然抖一下”的问题
    score = jerk * 2.0 + swing

    data_path = fc.data_path
    array_index = fc.array_index
    group_name = fc.group.name if fc.group else "Ungrouped"

    results.append({
        "score": score,
        "jerk": jerk,
        "swing": swing,
        "group": group_name,
        "path": data_path,
        "index": array_index,
    })

results.sort(key=lambda x: x["score"], reverse=True)

print(f"\n=== Frame {frame} 附近最抖的 F-Curves (Top {top_n}) ===")
for i, r in enumerate(results[:top_n], 1):
    print(
        f"{i:02d}. score={r['score']:.6f} | jerk={r['jerk']:.6f} | swing={r['swing']:.6f} | "
        f"{r['group']} | {r['path']}[{r['index']}]"
    )