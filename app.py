import io
import json
import os
import sys
import time
import uuid

import gradio as gr
import requests
import websocket
from PIL import Image

COMFYUI_SERVER = "127.0.0.1:8188"

WORKFLOW_OPTIONS = {
    "6C - 双ControlNet贴合（优先自然）": "图生图+LoRA (6C) (双ControlNet贴合).json",
    "6D - 贴合+轻立体（优先层次）": "图生图+LoRA (6D) (贴合+轻立体).json",
}

PRESETS = {
    "图生图+LoRA (6C) (双ControlNet贴合).json": {
        "title": "青瓷纹饰贴合优化",
        "positive": (
            "celadon bowl interior, dragon carving integrated into bowl surface, "
            "motif strictly follows bowl curvature and perspective, underglaze shallow relief carving, "
            "clear but soft engraved boundaries, subtle depth layering, mild recess shading, "
            "glaze pooling in carved grooves, preserve original celadon glaze tone and translucency"
        ),
        "negative": (
            "decal, sticker, printed texture, floating pattern, perspective mismatch, "
            "hard edges, sharp graphic outlines, plastic look, neon green, color shift, "
            "over-embossed deep sculpture, harsh cast shadows"
        ),
        "denoise": 0.42,
        "cn_strength": 0.92,
        "cfg": 9.0,
        "steps": 34,
    },
    "图生图+LoRA (6D) (贴合+轻立体).json": {
        "title": "青瓷纹饰轻立体增强",
        "positive": (
            "celadon bowl interior, dragon carving integrated into bowl surface, strict curvature conformity, "
            "underglaze relief carving with slightly stronger depth, clear carved paths with smooth transition, "
            "controlled shallow-to-mid depth layering, soft highlight on raised edges, gentle shadow in grooves, "
            "preserve celadon hue and glaze translucency"
        ),
        "negative": (
            "decal, sticker, printed texture, floating pattern, perspective mismatch, "
            "hard graphic edges, plastic look, neon green, color shift, deep 3d sculpture, harsh shadow carving"
        ),
        "denoise": 0.46,
        "cn_strength": 0.98,
        "cfg": 9.6,
        "steps": 36,
    },
}

CRAFT_INJECTION = {
    "关闭": {"positive": "", "negative": ""},
    "釉下浅刻（默认推荐）": {
        "positive": (
            "underglaze shallow carving, carving lines submerged beneath glaze, "
            "glaze pooling in grooves, soft depth transitions, subtle recess shading"
        ),
        "negative": "printed decal look, hard edge engraving, abrupt depth steps",
    },
    "轻浮雕（层次略增强）": {
        "positive": (
            "slight bas-relief under glaze, gentle highlight on raised edges, "
            "controlled mid-depth layering, soft ceramic micro-shadow"
        ),
        "negative": "deep sculpture relief, hard cast shadow, metallic edge highlights",
    },
    "老窑温润（偏自然）": {
        "positive": (
            "warm kiln-fired celadon character, subtle glaze variation, "
            "handcrafted irregular but coherent carved depth, natural translucent finish"
        ),
        "negative": "neon saturation, plastic smoothness, synthetic uniform texture",
    },
}


def _default_workflow_file() -> str:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg in PRESETS:
        return arg
    return WORKFLOW_OPTIONS["6C - 双ControlNet贴合（优先自然）"]


def _workflow_label_from_file(workflow_file: str) -> str:
    for label, file_name in WORKFLOW_OPTIONS.items():
        if file_name == workflow_file:
            return label
    return next(iter(WORKFLOW_OPTIONS.keys()))


DEFAULT_WORKFLOW_FILE = _default_workflow_file()
DEFAULT_WORKFLOW_LABEL = _workflow_label_from_file(DEFAULT_WORKFLOW_FILE)
DEFAULT_CONFIG = PRESETS[DEFAULT_WORKFLOW_FILE]


def upload_to_comfy(img: Image.Image, fallback_name: str) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    files = {"image": (fallback_name, buf.getvalue())}
    res = requests.post(f"http://{COMFYUI_SERVER}/upload/image", files=files, timeout=60)
    res.raise_for_status()
    return res.json()["name"]


def load_workflow(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_prompt(base: str, addon: str, strength: float) -> str:
    addon = addon.strip()
    if not addon:
        return base
    base = base.strip()
    weight = max(0.1, min(2.0, float(strength)))
    weighted = f"({addon}:{weight:.2f})"
    if not base:
        return weighted
    return f"{base}, {weighted}"


def apply_craft_injection(pos_prompt: str, neg_prompt: str, craft_mode: str, craft_strength: float):
    craft = CRAFT_INJECTION.get(craft_mode, CRAFT_INJECTION["关闭"])
    pos_final = append_prompt(pos_prompt, craft["positive"], craft_strength)
    neg_final = append_prompt(neg_prompt, craft["negative"], craft_strength)
    return pos_final, neg_final


def set_text_inputs(workflow: dict, positive: str, negative: str) -> None:
    for node_id in ("7", "5"):
        if node_id in workflow and "text" in workflow[node_id].get("inputs", {}):
            workflow[node_id]["inputs"]["text"] = positive
    for node_id in ("8", "6"):
        if node_id in workflow and "text" in workflow[node_id].get("inputs", {}):
            workflow[node_id]["inputs"]["text"] = negative


def set_dimension_inputs(workflow: dict, width: int, height: int) -> None:
    for node_id in ("9", "14", "167"):
        if node_id in workflow:
            node_inputs = workflow[node_id].get("inputs", {})
            if "width" in node_inputs:
                node_inputs["width"] = int(width)
            if "height" in node_inputs:
                node_inputs["height"] = int(height)


def set_sampler_inputs(workflow: dict, denoise: float, cfg: float, steps: int) -> None:
    for node in workflow.values():
        if node.get("class_type") != "KSampler":
            continue
        node_inputs = node.get("inputs", {})
        node_inputs["denoise"] = float(denoise)
        node_inputs["cfg"] = float(cfg)
        node_inputs["steps"] = int(steps)
        node_inputs["seed"] = int(time.time() * 1000) % 2_147_483_647


def set_controlnet_strength(workflow: dict, strength: float) -> None:
    for node in workflow.values():
        class_type = node.get("class_type", "")
        if class_type.startswith("ControlNetApply"):
            node_inputs = node.get("inputs", {})
            if "strength" in node_inputs:
                node_inputs["strength"] = float(strength)


def fetch_output_image_bytes(prompt_id: str) -> bytes:
    history = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}", timeout=60).json()
    outputs = history[prompt_id]["outputs"]

    image_data = None
    for preferred in ("14", "8"):
        if preferred in outputs and outputs[preferred].get("images"):
            image_data = outputs[preferred]["images"][0]
            break
    if image_data is None:
        for output in outputs.values():
            if output.get("images"):
                image_data = output["images"][0]
                break
    if image_data is None:
        raise gr.Error("未在 ComfyUI 输出中找到图片结果。")

    params = (
        f"filename={image_data['filename']}"
        f"&subfolder={image_data['subfolder']}"
        f"&type={image_data['type']}"
    )
    resp = requests.get(f"http://{COMFYUI_SERVER}/view?{params}", timeout=60)
    resp.raise_for_status()
    return resp.content


def main_process(
    vessel_img,
    pattern_img,
    workflow_label,
    craft_mode,
    craft_strength,
    pos_prompt,
    neg_prompt,
    denoise,
    cn_strength,
    cfg,
    steps,
    width,
    height,
    progress=gr.Progress(),
):
    if vessel_img is None:
        raise gr.Error("请先上传器皿图片。")
    if pattern_img is None:
        raise gr.Error("请先上传图案图片。")
    if workflow_label not in WORKFLOW_OPTIONS:
        raise gr.Error("请选择有效的工作流。")

    workflow_file = WORKFLOW_OPTIONS[workflow_label]
    pos_final, neg_final = apply_craft_injection(pos_prompt, neg_prompt, craft_mode, craft_strength)

    progress(0.08, desc="上传器皿图到 ComfyUI...")
    vessel_file = upload_to_comfy(vessel_img, "vessel_input.png")

    progress(0.15, desc="上传图案图到 ComfyUI...")
    pattern_file = upload_to_comfy(pattern_img, "pattern_input.png")

    progress(0.22, desc="加载并注入工作流参数...")
    workflow = load_workflow(workflow_file)

    if "2" in workflow:
        workflow["2"]["inputs"]["image"] = vessel_file
    if "3" in workflow:
        workflow["3"]["inputs"]["image"] = pattern_file

    set_text_inputs(workflow, pos_final, neg_final)
    set_dimension_inputs(workflow, width, height)
    set_sampler_inputs(workflow, denoise, cfg, steps)
    set_controlnet_strength(workflow, cn_strength)

    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}")
    try:
        payload = {"prompt": workflow, "client_id": client_id}
        res = requests.post(f"http://{COMFYUI_SERVER}/prompt", json=payload, timeout=60).json()
        prompt_id = res["prompt_id"]

        while True:
            out = ws.recv()
            if not isinstance(out, str):
                continue
            msg = json.loads(out)
            if msg.get("type") == "progress":
                data = msg.get("data", {})
                v = data.get("value", 0)
                m = max(data.get("max", 1), 1)
                progress(0.25 + (v / m) * 0.68, desc=f"生成中 ({v}/{m})...")
            if msg.get("type") == "executing" and msg.get("data", {}).get("node") is None:
                break
    finally:
        ws.close()

    progress(0.95, desc="拉取生成结果...")
    img_res = fetch_output_image_bytes(prompt_id)

    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    img_filename = f"{output_dir}/celadon_{timestamp}.png"
    with open(img_filename, "wb") as f:
        f.write(img_res)

    param_filename = f"{output_dir}/celadon_{timestamp}.json"
    metadata = {
        "source_workflow": workflow_file,
        "workflow_label": workflow_label,
        "craft_mode": craft_mode,
        "craft_strength": craft_strength,
        "positive_prompt": pos_prompt,
        "negative_prompt": neg_prompt,
        "positive_prompt_injected": pos_final,
        "negative_prompt_injected": neg_final,
        "params": {
            "denoise": denoise,
            "cn_strength": cn_strength,
            "cfg": cfg,
            "steps": steps,
            "size": f"{width}x{height}",
        },
        "timestamp": timestamp,
    }
    with open(param_filename, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    progress(1.0, desc="完成")
    return Image.open(io.BytesIO(img_res))


def get_vessel_size(img):
    if img is None:
        return 1024, 1204
    return img.size


def load_preset(workflow_label):
    workflow_file = WORKFLOW_OPTIONS.get(workflow_label, DEFAULT_WORKFLOW_FILE)
    conf = PRESETS[workflow_file]
    return conf["positive"], conf["negative"], conf["denoise"], conf["cn_strength"], conf["cfg"], conf["steps"]


with gr.Blocks(title=f"TakeChinaHome - {DEFAULT_CONFIG['title']}") as demo:
    gr.Markdown("# TakeChinaHome - 青瓷图生图（器皿 + 图案双图输入）")

    with gr.Row():
        with gr.Column():
            workflow_choice = gr.Dropdown(
                choices=list(WORKFLOW_OPTIONS.keys()),
                value=DEFAULT_WORKFLOW_LABEL,
                label="工作流版本",
            )

            craft_mode = gr.Dropdown(
                choices=list(CRAFT_INJECTION.keys()),
                value="釉下浅刻（默认推荐）",
                label="工艺注入",
            )
            craft_strength = gr.Slider(0.6, 1.4, value=1.0, step=0.05, label="工艺注入强度")

            vessel_in = gr.Image(type="pil", label="1. 上传器皿图片（必填）")
            pattern_in = gr.Image(type="pil", label="2. 上传图案图片（必填）")

            with gr.Row():
                width_s = gr.Slider(256, 2048, value=1024, step=64, label="宽度")
                height_s = gr.Slider(256, 2048, value=1204, step=64, label="高度")
            vessel_in.change(get_vessel_size, inputs=[vessel_in], outputs=[width_s, height_s])

            with gr.Tab("提示词"):
                pos_in = gr.Textbox(label="正向提示词 (Positive)", lines=5, value=DEFAULT_CONFIG["positive"])
                neg_in = gr.Textbox(label="负向提示词 (Negative)", lines=4, value=DEFAULT_CONFIG["negative"])

            with gr.Tab("参数"):
                with gr.Row():
                    denoise = gr.Slider(0.1, 1.0, value=DEFAULT_CONFIG["denoise"], step=0.01, label="重绘强度")
                    cn_s = gr.Slider(0.3, 1.5, value=DEFAULT_CONFIG["cn_strength"], step=0.01, label="ControlNet 强度")
                with gr.Row():
                    cfg_s = gr.Slider(1.0, 20.0, value=DEFAULT_CONFIG["cfg"], step=0.1, label="CFG")
                    step_s = gr.Slider(10, 60, value=DEFAULT_CONFIG["steps"], step=1, label="采样步数")

            run_btn = gr.Button("开始生成", variant="primary")

        with gr.Column():
            img_out = gr.Image(label="3. 结果预览")

    workflow_choice.change(
        load_preset,
        inputs=[workflow_choice],
        outputs=[pos_in, neg_in, denoise, cn_s, cfg_s, step_s],
    )

    run_btn.click(
        main_process,
        [
            vessel_in,
            pattern_in,
            workflow_choice,
            craft_mode,
            craft_strength,
            pos_in,
            neg_in,
            denoise,
            cn_s,
            cfg_s,
            step_s,
            width_s,
            height_s,
        ],
        img_out,
    )

if __name__ == "__main__":
    demo.launch()
