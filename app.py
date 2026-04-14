import gradio as gr
import json
import requests
import websocket
import uuid
import io
import time
import sys
from PIL import Image

# --- 基础配置 ---
COMFYUI_SERVER = "127.0.0.1:8188"
CLIENT_ID = str(uuid.uuid4())

# --- 模式预设配置表 ---
# 这样你以后增加新模式，只需要在这里加一行
PRESETS = {
    "图生图+LoRA (2).json": {
        "title": "青瓷私人定制系统",
        "positive": "(celadon sculpture:1.5), (jade-like texture:1.2), (smooth glossy ceramic glaze:1.4), light seafoam green color, 8k best quality",
        "negative": "text, watermark, blurry, low quality, distorted, metal, plastic",
        "denoise": 0.90,
        "cn_strength": 0.8
    },
    "图生图+LoRA (1).json": {
        "title": "常用图生图工作流",
        "positive": "masterpiece, best quality, highly detailed, realistic, vivid colors",
        "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
        "denoise": 0.60,
        "cn_strength": 0.6
    }
}

# 获取当前运行的文件名，如果没有参数则默认为青瓷 (2)
current_file = sys.argv[1] if len(sys.argv) > 1 else "图生图+LoRA (2).json"
# 获取对应的预设，如果文件名不在表里，就给个默认值
config = PRESETS.get(current_file, PRESETS["图生图+LoRA (1).json"])

def upload_to_comfy(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    files = {"image": ("input_img.png", buf.getvalue())}
    res = requests.post(f"http://{COMFYUI_SERVER}/upload/image", files=files)
    return res.json()["name"]

def main_process(input_img, pos_prompt, neg_prompt, denoise, cn_strength, cfg, steps, progress=gr.Progress()):
    progress(0.1, desc="正在同步配置...")
    filename = upload_to_comfy(input_img)
    
    with open(current_file, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # 动态注入参数 (基于你导出的 API 节点 ID)
    if "2" in workflow: workflow["2"]["inputs"]["image"] = filename
    if "5" in workflow: workflow["5"]["inputs"]["text"] = pos_prompt    # 正面词
    if "6" in workflow: workflow["6"]["inputs"]["text"] = neg_prompt    # 负面词
    if "7" in workflow: 
        workflow["7"]["inputs"]["denoise"] = denoise
        workflow["7"]["inputs"]["cfg"] = cfg
        workflow["7"]["inputs"]["steps"] = int(steps)
        workflow["7"]["inputs"]["seed"] = int(time.time())
    if "17" in workflow: workflow["17"]["inputs"]["strength"] = cn_strength

    # 执行并监听
    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={CLIENT_ID}")
    p = {"prompt": workflow, "client_id": CLIENT_ID}
    res = requests.post(f"http://{COMFYUI_SERVER}/prompt", json=p).json()
    prompt_id = res['prompt_id']

    while True:
        out = ws.recv()
        if isinstance(out, str):
            msg = json.loads(out)
            if msg['type'] == 'progress':
                v, m = msg['data']['value'], msg['data']['max']
                progress(0.2 + (v/m) * 0.7, desc=f"渲染中 ({v}/{m})...")
            if msg['type'] == 'executing' and msg['data']['node'] is None:
                break
    
    history = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}").json()
    output_data = history[prompt_id]['outputs']['8']['images'][0]
    img_res = requests.get(f"http://{COMFYUI_SERVER}/view?filename={output_data['filename']}&subfolder={output_data['subfolder']}&type={output_data['type']}").content
    ws.close()
    return Image.open(io.BytesIO(img_res))

# --- Gradio UI 界面 ---
with gr.Blocks(title=f"TakeChinaHome - {config['title']}") as demo:
    gr.Markdown(f"# 🏺 TakeChinaHome - {config['title']}")
    gr.Markdown(f"当前加载工作流文件: `{current_file}`")
    
    with gr.Row():
        with gr.Column():
            img_in = gr.Image(type="pil", label="1. 输入底图")
            
            with gr.Tab("提示词设置"):
                pos_in = gr.Textbox(label="正面提示词 (Positive)", lines=4, value=config['positive'])
                neg_in = gr.Textbox(label="负面提示词 (Negative)", lines=3, value=config['negative'])
            
            with gr.Tab("参数精调"):
                with gr.Row():
                    denoise = gr.Slider(0.1, 1.0, value=config['denoise'], step=0.01, label="重绘强度")
                    cn_s = gr.Slider(0.0, 1.5, value=config['cn_strength'], step=0.1, label="特征保持强度")
                with gr.Row():
                    cfg_s = gr.Slider(1.0, 20.0, value=7.0, step=0.5, label="CFG 指导系数")
                    step_s = gr.Slider(10, 50, value=25, step=1, label="采样步数")
            
            run_btn = gr.Button("🚀 开始执行生成", variant="primary")
            
        with gr.Column():
            img_out = gr.Image(label="3. 生成结果预览")

    run_btn.click(main_process, [img_in, pos_in, neg_in, denoise, cn_s, cfg_s, step_s], img_out)

if __name__ == "__main__":
    demo.launch()